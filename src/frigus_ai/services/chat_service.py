"""Casos de uso de chat — `service` (abaixo) é o ponto de entrada único de todas as
interfaces (API, A2A, MCP, TUI)."""

import asyncio
from base64 import b64encode
from collections.abc import AsyncIterator
from uuid import uuid4

from frigus_ai.exceptions import ChatDeOutroUsuario, LimiteDeMensagensExcedido
from frigus_ai.graph.llm import llm_rapido
from frigus_ai.graph.prompts import load_prompt
from frigus_ai.infra.redis.rate_limit import can_send_message
from frigus_ai.logging import Logging
from frigus_ai.repositories import chat_embeddings_repository, chat_repository
from frigus_ai.repositories.chat_repository import ChatDocument
from frigus_ai.schemas.execution import AnswerReady, ExecutionEvent, RunFailed
from frigus_ai.schemas.models import ChatMessage, Fatos, Resumo, Role
from frigus_ai.services import runner
from frigus_ai.services.user_service import user_service
from frigus_ai.types import novo_chat_id

logger = Logging.get_logger(__name__)

# A cada N mensagens salvas (user + AI juntos, então N=10 é a cada 5 turnos) fatos e
# resumo são atualizados em segundo plano — ver `_talvez_atualizar_memoria`.
_INTERVALO_ATUALIZACAO_MEMORIA = 10
# Menos que 2 turnos não é conversa que valha lembrar ("oi"/"olá"): nem chama LLM.
_MINIMO_MENSAGENS_MEMORIA = 4
# Doc antigo, sem `resumido_ate`, mandaria o histórico inteiro de uma vez pro resumidor.
_JANELA_MAXIMA = 40
# Chats abandonados resumidos quando o usuário abre um novo — teto pra não virar rajada.
_PENDENTES_POR_NOVO_CHAT = 3

llm_fatos = llm_rapido.with_structured_output(Fatos) if llm_rapido else None
llm_resumo = llm_rapido.with_structured_output(Resumo) if llm_rapido else None

# Referências das tarefas de fire-and-forget: sem isso, o event loop pode coletar a
# task no meio da execução (ninguém mais segura o objeto) — padrão recomendado pela
# doc do asyncio pra `create_task` sem `await`. `send_message`/`stream_message` são o
# ponto de entrada único de chat (API, A2A, MCP, TUI), por isso o disparo mora aqui, e
# não em `BackgroundTasks` do FastAPI (só existe dentro de uma rota HTTP).
_tarefas_em_segundo_plano: set[asyncio.Task] = set()


def _disparar_em_segundo_plano(coro) -> None:
    tarefa = asyncio.create_task(coro)
    _tarefas_em_segundo_plano.add(tarefa)
    tarefa.add_done_callback(_tarefas_em_segundo_plano.discard)


def _atualizar_resumo(resumo_atual: str, mensagens_recentes: list[dict]) -> Resumo | None:
    if llm_resumo is None:  # provider sem API key configurada
        return None

    logger.info("Atualizando resumo da conversa...")

    conversa = "\n".join(f"{msg['role']}: {msg['content']}" for msg in mensagens_recentes)

    resumo = llm_resumo.invoke(
        load_prompt("resumidor").format(resumo_atual=resumo_atual, mensagens=conversa)
    )
    assert isinstance(resumo, Resumo)
    return resumo


def _extrair_fatos(mensagens_recentes: list[dict], fatos_atuais: Fatos) -> Fatos | None:
    if llm_fatos is None:  # provider sem API key configurada — feature opcional
        return None

    logger.info("Extraindo fatos da conversa...")

    conversa = "\n".join(f"{msg['role']}: {msg['content']}" for msg in mensagens_recentes)
    prompt = load_prompt("fatos").format(
        fatos_atuais=fatos_atuais.model_dump_json(), mensagens=conversa
    )
    fatos = llm_fatos.invoke(prompt)
    assert isinstance(fatos, Fatos)
    return fatos


class ChatService:
    """Casos de uso de chat; a instância (`service`, abaixo) é o ponto de entrada."""

    async def iniciar_sessao(self, user_id: str) -> int | None:
        """Resolve o stock_id do usuário."""

        return await user_service.resolver_stock_id(user_id)

    async def criar_chat(self, user_id: str) -> str:
        await self.iniciar_sessao(user_id)
        chat_id = novo_chat_id()
        await chat_repository.criar_chat(chat_id, user_id)
        _disparar_em_segundo_plano(self._resumir_pendentes(user_id))
        return chat_id

    async def validar_ownership(self, session_id: str, user_id: str) -> None:
        dono = await chat_repository.buscar_dono_chat(session_id)
        if dono is None:
            return
        if dono != user_id:
            raise ChatDeOutroUsuario(session_id)

    async def listar_chats(self, user_id: str) -> list[ChatDocument]:
        return await chat_repository.listar_chats(user_id)

    async def garantir_limite(self, user_id: str) -> None:
        """Consome uma unidade do rate limit; levanta se o usuário estourou a janela."""

        if not await asyncio.to_thread(can_send_message, user_id):
            raise LimiteDeMensagensExcedido(
                "Você atingiu o limite de mensagens. Tente novamente em alguns instantes."
            )

    async def send_message(
        self, conteudo: str, session_id: str, user_id: str, stock_id: int | None
    ) -> str:
        await self.garantir_limite(user_id)

        resposta = await runner.executar(conteudo, session_id, user_id, stock_id)

        if not resposta:
            return "Sem resposta."

        novas = [
            ChatMessage(role=Role.HUMAN, content=conteudo),
            ChatMessage(role=Role.AI, content=resposta),
        ]
        await chat_repository.salvar_mensagens(user_id, session_id, novas)
        await self._talvez_atualizar_memoria(session_id, user_id)

        return resposta

    async def stream_message(
        self, conteudo: str, session_id: str, user_id: str, stock_id: int | None
    ) -> AsyncIterator[ExecutionEvent]:
        """
        Mesmo caso de uso do `send_message` (grafo, persistência), só que emitindo a
        timeline de execução (`schemas/execution.py`) enquanto o grafo roda.

        **Não** chama `garantir_limite` aqui de propósito: o corpo de um gerador só roda
        depois que a resposta HTTP começou, quando 429 já não é possível. Quem consome
        o limite no caminho SSE é a dependência da rota, antes de abrir o stream — e
        `can_send_message` incrementa contador, então chamar nos dois lugares cobraria
        duas mensagens por request.
        """

        resposta = ""

        async for evento in runner.executar_stream(conteudo, session_id, user_id, stock_id):
            if isinstance(evento, AnswerReady):
                resposta = evento.content
            elif isinstance(evento, RunFailed):
                resposta = evento.message
            yield evento

        novas = [
            ChatMessage(role=Role.HUMAN, content=conteudo),
            ChatMessage(role=Role.AI, content=resposta or "Sem resposta."),
        ]
        await chat_repository.salvar_mensagens(user_id, session_id, novas)
        await self._talvez_atualizar_memoria(session_id, user_id)

    async def _talvez_atualizar_memoria(self, session_id: str, user_id: str) -> None:
        """
        Dispara fatos + resumo em segundo plano a cada `_INTERVALO_ATUALIZACAO_MEMORIA`
        mensagens — chamado depois de salvar, então o próprio `salvar_mensagens` já
        contou. Não bloqueia a resposta do usuário com uma chamada de LLM extra.

        Substitui depender do fechamento explícito da sessão (`encerrar_sessao`) pra
        ter resumo: sessão que o usuário nunca fecha (fecha o terminal, some sem
        `DELETE /chats/{id}`) ficava com `resume` vazio pra sempre.
        """

        total = await chat_repository.contar_mensagens(session_id, user_id)
        if total % _INTERVALO_ATUALIZACAO_MEMORIA == 0:
            _disparar_em_segundo_plano(self._atualizar_memoria(session_id, user_id))

    async def _resumir_pendentes(self, user_id: str) -> None:
        """
        Chat que o usuário abandonou sem `DELETE` (e sem bater o intervalo) nunca teria
        resumo. Abrir um chat novo é o sinal de que os anteriores acabaram — resume o que
        faltou neles, sem precisar de cron.

        Em sequência, não em paralelo: todos atualizam os fatos do MESMO usuário, e dois
        merges concorrentes perderiam o que o outro gravou.
        """

        try:
            pendentes = await chat_repository.listar_pendentes_de_resumo(
                user_id, _MINIMO_MENSAGENS_MEMORIA, _PENDENTES_POR_NOVO_CHAT
            )
        except Exception:
            logger.exception(f"Falha ao listar chats pendentes de resumo | user_id={user_id}")
            return

        for session_id in pendentes:
            await self._atualizar_memoria(session_id, user_id)

    async def _atualizar_memoria(self, session_id: str, user_id: str) -> None:
        """
        Fatos e resumo lêem as mesmas mensagens — só as que o resumo ainda não cobre
        (`resumido_ate`) — numa leitura só do documento pros dois.
        """

        try:
            doc = await chat_repository.buscar_documento_completo(session_id, user_id)
            if not doc:
                return

            mensagens = doc.get("messages") or []
            recentes = mensagens[doc.get("resumido_ate", 0):][-_JANELA_MAXIMA:]
            if len(mensagens) < _MINIMO_MENSAGENS_MEMORIA or not recentes:
                return

            fatos_atuais = await user_service.buscar_fatos(user_id)
            fatos_extraidos = await asyncio.to_thread(_extrair_fatos, recentes, fatos_atuais)
            if fatos_extraidos is not None:
                await user_service.atualizar_fatos_por_extracao(user_id, fatos_extraidos)

            resumo = await asyncio.to_thread(_atualizar_resumo, doc.get("resume", ""), recentes)
            if resumo is None:
                return

            await chat_repository.salvar_resumo(
                resumo.resumo, session_id, user_id, resumido_ate=len(mensagens)
            )
        except Exception:
            logger.exception(f"Falha ao atualizar memória em segundo plano | session_id={session_id}")
            return

        await self._indexar_resumo(session_id, user_id, resumo)

    async def _indexar_resumo(self, session_id: str, user_id: str, resumo: Resumo) -> None:
        """
        Só chat relevante vira embedding; um que deixou de ser (ou nunca foi) sai do
        índice. Falha aqui não desfaz o resumo no Mongo: o ponto fica velho até o
        próximo resumo daquele chat, que sobrescreve pelo mesmo ID.
        """

        try:
            if resumo.relevante:
                await chat_embeddings_repository.salvar_resumo(session_id, user_id, resumo.resumo)
            else:
                await chat_embeddings_repository.remover_resumo(session_id)
        except Exception:
            logger.exception(f"Falha ao indexar resumo no Qdrant | session_id={session_id}")

    async def analisar_foto(self, user_id: str, stock_id: int | None, imagem: bytes) -> str:
        """
        Foto da geladeira/freezer/despensa — não é uma conversa (não salva histórico,
        não conta pro rate limit de mensagens do chat). `thread_id` único por chamada,
        nunca reaproveitado: o checkpoint do grafo guarda `imagem_b64` (alguns MB em
        base64), e reusar uma thread faria o próximo turno de TEXTO nela ainda carregar
        essa imagem e cair de novo na Visão, em vez de ir pro roteador normal.

        Como ninguém volta a essa thread, ela é apagada no fim — senão cada foto deixava
        seus MB de base64 no Mongo pra sempre.
        """

        thread_id = f"visao-{user_id}-{uuid4()}"

        try:
            resposta = await runner.executar(
                "Analise esta foto da geladeira/freezer/despensa.",
                thread_id,
                user_id,
                stock_id,
                imagem_b64=b64encode(imagem).decode(),
            )
        finally:
            await runner.descartar_thread(thread_id)

        return resposta or "Não consegui analisar a foto."

    async def get_history(
        self, session_id: str, user_id: str, limit: int = 5
    ) -> list[ChatMessage]:
        return await chat_repository.buscar_historico(session_id, user_id, limit)

    async def encerrar_sessao(self, session_id: str, user_id: str) -> None:
        """
        Fatos/resumo já são mantidos frescos periodicamente durante a conversa
        (`_talvez_atualizar_memoria`) — aqui só cobre o rabo que ainda não bateu o
        intervalo. Se o ciclo periódico já cobriu tudo, `resumido_ate` bate com o total
        e `_atualizar_memoria` sai sem chamar LLM.
        """

        await self._atualizar_memoria(session_id, user_id)


service = ChatService()
