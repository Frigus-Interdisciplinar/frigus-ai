"""Casos de uso de chat; `service` é o ponto de entrada único (API, A2A, MCP, TUI)."""

import asyncio
import time
from base64 import b64encode
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from frigus_ai.domain.errors import ChatDeOutroUsuario, LimiteDeMensagensExcedido
from frigus_ai.domain.identifiers import novo_chat_id
from frigus_ai.domain.models import ChatMessage, Fatos, Resumo, Role
from frigus_ai.graph.llm import estruturado, llm_guardrail, llm_luna, llm_rapido
from frigus_ai.graph.prompts import load_prompt
from frigus_ai.infra.logging import Logging
from frigus_ai.infra.redis.rate_limit import can_send_message
from frigus_ai.repositories import chat_embeddings_repository, chat_repository
from frigus_ai.repositories.chat_repository import ChatDocument
from frigus_ai.schemas.execution import AnswerReady, ExecutionEvent, RunFailed
from frigus_ai.services import runner
from frigus_ai.services.user_service import user_service
from frigus_ai.telemetry.metrics import (
    BACKGROUND_TASKS,
    CHAT_PERSIST_FAILURES,
    MEMORY_PENDING,
    RATE_LIMIT_REJECTIONS,
    SSE_DISCONNECTS,
    medir_memoria,
)

logger = Logging.get_logger(__name__)


@dataclass(frozen=True)
class _Memoria:
    """Parâmetros da memória de longo prazo (fatos, resumo e embedding)."""

    intervalo_atualizacao: int = 10  # mensagens (user + AI): 10 = a cada 5 turnos
    minimo_mensagens: int = 4  # abaixo disso ("oi", "olá") nem chama LLM
    janela_maxima: int = 40  # teto de mensagens por chamada ao resumidor
    pendentes_por_novo_chat: int = 3  # chats abandonados resumidos ao abrir um novo
    intervalo_reconciliacao_s: float = 300
    inativo_ha: timedelta = timedelta(minutes=10)  # o reconciliador não disputa com chat ativo
    pendentes_por_ciclo: int = 20
    espera_apos_falha_s: float = 3600  # chat que falha não gasta LLM a cada ciclo
    esperas_persistencia_s: tuple[float, ...] = (1, 5)  # retry da gravação do turno


_MEM = _Memoria()

llm_fatos = estruturado(Fatos, llm_rapido, llm_guardrail, llm_luna)
llm_resumo = estruturado(Resumo, llm_rapido, llm_guardrail, llm_luna)

# Sem referência, o event loop pode coletar a task no meio (doc do asyncio sobre `create_task`).
_tarefas_em_segundo_plano: set[asyncio.Task] = set()
_falhou_em: dict[str, float] = {}


def _fim_da_tarefa(tarefa: asyncio.Task) -> None:
    _tarefas_em_segundo_plano.discard(tarefa)
    BACKGROUND_TASKS.set(len(_tarefas_em_segundo_plano))


def _disparar_em_segundo_plano(coro) -> None:
    tarefa = asyncio.create_task(coro)
    _tarefas_em_segundo_plano.add(tarefa)
    BACKGROUND_TASKS.set(len(_tarefas_em_segundo_plano))
    tarefa.add_done_callback(_fim_da_tarefa)


async def drenar_tarefas(timeout: float = 10.0) -> None:
    """Shutdown: espera as tarefas em voo; o que não terminar o reconciliador refaz."""

    if _tarefas_em_segundo_plano:
        await asyncio.wait(set(_tarefas_em_segundo_plano), timeout=timeout)


def _conversa(mensagens: list[dict]) -> str:
    return "\n".join(f"{msg['role']}: {msg['content']}" for msg in mensagens)


def _atualizar_resumo(resumo_atual: str, mensagens_recentes: list[dict]) -> Resumo | None:
    if llm_resumo is None:  # provider sem API key
        return None

    logger.info("Atualizando resumo da conversa...")
    prompt = load_prompt("resumidor").format(
        resumo_atual=resumo_atual, mensagens=_conversa(mensagens_recentes)
    )
    resumo = llm_resumo.invoke(prompt)
    if not isinstance(resumo, Resumo):
        raise TypeError(f"esperava Resumo, veio {type(resumo).__name__}")
    return resumo


def _extrair_fatos(mensagens_recentes: list[dict], fatos_atuais: Fatos) -> Fatos | None:
    if llm_fatos is None:  # provider sem API key
        return None

    logger.info("Extraindo fatos da conversa...")
    prompt = load_prompt("fatos").format(
        fatos_atuais=fatos_atuais.model_dump_json(), mensagens=_conversa(mensagens_recentes)
    )
    fatos = llm_fatos.invoke(prompt)
    if not isinstance(fatos, Fatos):
        raise TypeError(f"esperava Fatos, veio {type(fatos).__name__}")
    return fatos


class ChatService:
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
        # Chat inexistente não é erro: o cliente escolhe o id e o 1º envio cria o chat.
        dono = await chat_repository.buscar_dono_chat(session_id)
        if dono is not None and dono != user_id:
            raise ChatDeOutroUsuario(session_id)

    async def listar_chats(self, user_id: str) -> list[ChatDocument]:
        return await chat_repository.listar_chats(user_id)

    async def garantir_limite(self, user_id: str) -> None:
        """Consome uma unidade do rate limit; levanta se o usuário estourou a janela."""

        if not await asyncio.to_thread(can_send_message, user_id):
            RATE_LIMIT_REJECTIONS.labels(scope="mensagens").inc()
            raise LimiteDeMensagensExcedido(
                "Você atingiu o limite de mensagens. Tente novamente em alguns instantes."
            )

    async def send_message(
        self, conteudo: str, session_id: str, user_id: str, stock_id: int | None, imagem: bytes | None = None
    ) -> str:
        await self.garantir_limite(user_id)

        # `imagem_b64` só vai com foto: a foto viaja pelo contexto do grafo, nunca pelo histórico.
        extras = {"imagem_b64": b64encode(imagem).decode()} if imagem else {}
        resposta = await runner.executar(conteudo, session_id, user_id, stock_id, **extras)
        if not resposta:
            return "Sem resposta."

        await self._persistir_turno(conteudo, resposta, session_id, user_id, via="send")
        return resposta

    async def stream_message(
        self, conteudo: str, session_id: str, user_id: str, stock_id: int | None
    ) -> AsyncIterator[ExecutionEvent]:
        """
        Como `send_message`, emitindo a timeline de execução enquanto o grafo roda.

        Não chama `garantir_limite`: dentro do gerador o 429 já não é possível, e a dependência
        da rota consome o limite antes do stream (chamar nos dois cobraria duas mensagens).
        O turno é gravado no `finally`, numa task própria: cliente que fecha o SSE cancela
        este gerador e o turno sumia do histórico.
        """

        resposta = ""
        terminou = False

        try:
            async for evento in runner.executar_stream(conteudo, session_id, user_id, stock_id):
                if isinstance(evento, AnswerReady):
                    resposta = evento.content
                elif isinstance(evento, RunFailed):
                    resposta = evento.message
                yield evento
            terminou = True
        finally:
            if not terminou:
                SSE_DISCONNECTS.inc()
            _disparar_em_segundo_plano(self._persistir_turno(
                conteudo, resposta or "Sem resposta.", session_id, user_id, via="stream"
            ))

    async def _persistir_turno(
        self, conteudo: str, resposta: str, session_id: str, user_id: str, via: str
    ) -> None:
        """Grava pergunta + resposta com retry curto; se esgotar, loga e conta (sem 500)."""

        novas = [
            ChatMessage(role=Role.HUMAN, content=conteudo),
            ChatMessage(role=Role.AI, content=resposta),
        ]

        for espera in (*_MEM.esperas_persistencia_s, None):
            try:
                await chat_repository.salvar_mensagens(user_id, session_id, novas)
                break
            except Exception:
                if espera is None:
                    CHAT_PERSIST_FAILURES.labels(via=via).inc()
                    logger.exception("Turno não gravado no Mongo | session_id=%s", session_id)
                    return
                logger.warning("Falha ao gravar turno, tentando de novo em %ss", espera)
                await asyncio.sleep(espera)

        try:
            await self._talvez_atualizar_memoria(session_id, user_id)
        except Exception:
            logger.exception("Falha ao agendar memória | session_id=%s", session_id)

    async def _talvez_atualizar_memoria(self, session_id: str, user_id: str) -> None:
        """A cada `intervalo_atualizacao` mensagens, atualiza fatos + resumo em segundo plano."""

        total = await chat_repository.contar_mensagens(session_id, user_id)
        if total % _MEM.intervalo_atualizacao == 0:
            _disparar_em_segundo_plano(self._atualizar_memoria(session_id, user_id))

    async def _resumir_pendentes(self, user_id: str) -> None:
        """Abrir um chat novo sinaliza que os anteriores acabaram: resume o que ficou pendente.

        Em sequência: todos atualizam os fatos do mesmo usuário, e merges concorrentes perderiam dados.
        """

        try:
            pendentes = await chat_repository.listar_pendentes_de_resumo(
                user_id, _MEM.minimo_mensagens, _MEM.pendentes_por_novo_chat
            )
        except Exception:
            logger.exception("Falha ao listar chats pendentes de resumo | user_id=%s", user_id)
            return

        for session_id in pendentes:
            await self._atualizar_memoria(session_id, user_id)

    async def _atualizar_memoria(self, session_id: str, user_id: str) -> bool:
        """
        Extrai fatos e resume só o que o resumo ainda não cobre (`resumido_ate`), depois
        garante o embedding, inclusive o que ficou pra trás (`indexado_ate` < `resumido_ate`).
        Devolve `False` se alguma etapa falhou (já logada).
        """

        try:
            doc = await chat_repository.buscar_documento_completo(session_id, user_id)
            if not doc:
                return True

            mensagens = doc.get("messages") or []
            recentes = mensagens[doc.get("resumido_ate", 0):][-_MEM.janela_maxima:]

            if len(mensagens) >= _MEM.minimo_mensagens and recentes:
                with medir_memoria("fatos"):
                    fatos_atuais = await user_service.buscar_fatos(user_id)
                    fatos_extraidos = await asyncio.to_thread(_extrair_fatos, recentes, fatos_atuais)
                    if fatos_extraidos is not None:
                        await user_service.atualizar_fatos_por_extracao(user_id, fatos_extraidos)

                with medir_memoria("resumo"):
                    resumo = await asyncio.to_thread(_atualizar_resumo, doc.get("resume", ""), recentes)
                    if resumo is not None:
                        await chat_repository.salvar_resumo(
                            resumo.resumo, session_id, user_id,
                            resumido_ate=len(mensagens), relevante=resumo.relevante,
                        )
                        doc["resume"], doc["resume_relevante"] = resumo.resumo, resumo.relevante
                        doc["resumido_ate"] = len(mensagens)
        except Exception:
            logger.exception("Falha ao atualizar memória em segundo plano | session_id=%s", session_id)
            return False

        resumido_ate = doc.get("resumido_ate", 0)
        if "resume_relevante" in doc and resumido_ate > doc.get("indexado_ate", 0):
            return await self._indexar_resumo(
                session_id, user_id, Resumo(resumo=doc["resume"], relevante=doc["resume_relevante"]),
                resumido_ate,
            )
        return True

    async def _indexar_resumo(
        self, session_id: str, user_id: str, resumo: Resumo, resumido_ate: int
    ) -> bool:
        """
        Só chat relevante vira embedding; o que deixou de ser sai do índice. `indexado_ate`
        só avança depois do Qdrant confirmar, então uma falha é refeita sem chamar o LLM.
        """

        try:
            with medir_memoria("embedding"):
                if resumo.relevante:
                    await chat_embeddings_repository.salvar_resumo(session_id, user_id, resumo.resumo)
                else:
                    await chat_embeddings_repository.remover_resumo(session_id)
                await chat_repository.marcar_indexado(session_id, user_id, resumido_ate)
        except Exception:
            logger.exception("Falha ao indexar resumo no Qdrant | session_id=%s", session_id)
            return False
        return True

    async def reconciliar_memoria(self) -> None:
        """Um ciclo: refaz resumo/embedding de chats parados, de qualquer usuário, em sequência."""

        pendentes, total = await chat_repository.listar_pendentes_globais(
            _MEM.minimo_mensagens, _MEM.inativo_ha, _MEM.pendentes_por_ciclo
        )
        MEMORY_PENDING.set(total)

        agora = time.monotonic()
        for pendente in pendentes:
            session_id = pendente["session_id"]
            if agora - _falhou_em.get(session_id, -_MEM.espera_apos_falha_s) < _MEM.espera_apos_falha_s:
                continue

            if await self._atualizar_memoria(session_id, pendente["user_id"]):
                _falhou_em.pop(session_id, None)
            else:
                _falhou_em[session_id] = time.monotonic()

    async def reconciliar_memoria_loop(
        self, intervalo_s: float = _MEM.intervalo_reconciliacao_s
    ) -> None:
        """
        Roda até ser cancelado (lifespan da API). O estado é o próprio doc do Mongo
        (`resumido_ate`/`indexado_ate`), então um restart não perde nada.

        ponytail: um loop por processo; com vários workers o mesmo chat pode ser resumido 2x
        (custo, não corrupção). Lock no Redis se escalar.
        """

        if llm_resumo is None:
            logger.info("Sem LLM de resumo configurado, reconciliador de memória desligado.")
            return

        # Dorme antes do 1º ciclo pra não processar backlog a cada boot/reload.
        while True:
            await asyncio.sleep(intervalo_s)
            try:
                await self.reconciliar_memoria()
            except Exception:
                logger.exception("Ciclo do reconciliador de memória falhou")

    async def analisar_foto(self, user_id: str, stock_id: int | None, imagem: bytes) -> str:
        """
        Foto da geladeira: não é conversa (sem histórico, sem rate limit de chat). O `thread_id` é
        único e apagado no fim, pra não deixar checkpoint de uma análise avulsa.
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
        self, session_id: str, user_id: str, limit: int | None = None
    ) -> list[ChatMessage]:
        return await chat_repository.buscar_historico(session_id, user_id, limit)

    async def encerrar_sessao(self, session_id: str, user_id: str) -> None:
        """Cobre o que ainda não bateu o intervalo; se já está tudo resumido, não chama LLM."""

        await self._atualizar_memoria(session_id, user_id)


service = ChatService()
