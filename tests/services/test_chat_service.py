"""
Orquestração de fatos/resumo em `ChatService`: atualizados periodicamente durante a
conversa (`_talvez_atualizar_memoria`, a cada N mensagens), no fechamento da sessão e
quando o usuário abre um chat novo (`_resumir_pendentes`) — chat abandonado não pode
ficar sem resumo. Só o que o resumo ainda não cobre (`resumido_ate`) vai pro LLM, chat
curto demais não gasta LLM, e só resumo `relevante` vira embedding. Tudo mockado
(repositories/user_service); a query em si tem teste em tests/repositories/.
"""

import asyncio

import pytest

from frigus_ai.domain.errors import ChatDeOutroUsuario, ChatNaoEncontrado
from frigus_ai.domain.models import Fatos, Resumo
from frigus_ai.repositories import chat_embeddings_repository, chat_repository
from frigus_ai.schemas.execution import AnswerReady, RunFailed, RunStarted
from frigus_ai.services import chat_service as chat_service_module
from frigus_ai.services import runner
from frigus_ai.services.chat_service import service as chat_service
from frigus_ai.services.user_service import user_service


def _msgs(n):
    return [{"role": "human" if i % 2 == 0 else "ai", "content": f"msg {i}"} for i in range(n)]


@pytest.fixture
def memoria(monkeypatch):
    """Stuba tudo que `_atualizar_memoria` toca e registra as chamadas."""

    registro = {"doc": None, "resumo": Resumo(resumo="resumo novo", relevante=True),
                "fatos": None, "chamadas_resumo": [], "salvou": [], "indexou": [],
                "removeu": [], "fatos_salvos": [], "indexado_ate": []}

    async def _doc(session_id, user_id):
        return registro["doc"]

    async def _buscar_fatos(user_id):
        return Fatos()

    def _atualizar_resumo(atual, msgs):
        registro["chamadas_resumo"].append((atual, msgs))
        return registro["resumo"]

    async def _salvar_resumo(resumo, session_id, user_id, resumido_ate, relevante):
        registro["salvou"].append((resumo, session_id, user_id, resumido_ate))

    async def _marcar_indexado(session_id, user_id, indexado_ate):
        registro["indexado_ate"].append(indexado_ate)

    async def _indexar(session_id, user_id, resumo):
        registro["indexou"].append((session_id, user_id, resumo))

    async def _remover(session_id):
        registro["removeu"].append(session_id)

    async def _atualizar_fatos(user_id, fatos):
        registro["fatos_salvos"].append((user_id, fatos))

    monkeypatch.setattr(chat_repository, "buscar_documento_completo", _doc)
    monkeypatch.setattr(chat_repository, "salvar_resumo", _salvar_resumo)
    monkeypatch.setattr(chat_repository, "marcar_indexado", _marcar_indexado)
    monkeypatch.setattr(user_service, "buscar_fatos", _buscar_fatos)
    monkeypatch.setattr(user_service, "atualizar_fatos_por_extracao", _atualizar_fatos)
    monkeypatch.setattr(chat_service_module, "_extrair_fatos", lambda m, a: registro["fatos"])
    monkeypatch.setattr(chat_service_module, "_atualizar_resumo", _atualizar_resumo)
    monkeypatch.setattr(chat_embeddings_repository, "salvar_resumo", _indexar)
    monkeypatch.setattr(chat_embeddings_repository, "remover_resumo", _remover)
    return registro


async def test_talvez_atualizar_memoria_dispara_no_multiplo_do_intervalo(monkeypatch):
    async def _contar(session_id, user_id):
        return 10

    monkeypatch.setattr(chat_repository, "contar_mensagens", _contar)

    disparadas = []
    monkeypatch.setattr(chat_service_module, "_disparar_em_segundo_plano", disparadas.append)

    await chat_service._talvez_atualizar_memoria("sessao-1", "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c")

    assert len(disparadas) == 1
    disparadas[0].close()  # não executa o corpo — só confirma que foi agendado


async def test_talvez_atualizar_memoria_nao_dispara_fora_do_intervalo(monkeypatch):
    async def _contar(session_id, user_id):
        return 7

    monkeypatch.setattr(chat_repository, "contar_mensagens", _contar)

    disparadas = []
    monkeypatch.setattr(chat_service_module, "_disparar_em_segundo_plano", disparadas.append)

    await chat_service._talvez_atualizar_memoria("sessao-1", "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c")

    assert disparadas == []


async def test_resumo_recebe_so_o_que_ainda_nao_foi_resumido(memoria):
    memoria["doc"] = {"messages": _msgs(15), "resume": "resumo salvo", "resumido_ate": 10}

    await chat_service._atualizar_memoria("sessao-1", "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c")

    [(resumo_atual, recentes)] = memoria["chamadas_resumo"]
    assert resumo_atual == "resumo salvo"
    assert [m["content"] for m in recentes] == [f"msg {i}" for i in range(10, 15)]
    assert memoria["salvou"] == [("resumo novo", "sessao-1", "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c", 15)]


async def test_chat_ja_resumido_nao_chama_llm(memoria):
    """Fecha a sessão logo depois do ciclo periódico: nada novo, nada a fazer."""

    memoria["doc"] = {"messages": _msgs(10), "resume": "r", "resumido_ate": 10}

    await chat_service.encerrar_sessao("sessao-1", user_id="3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c")

    assert memoria["chamadas_resumo"] == []
    assert memoria["salvou"] == []


async def test_chat_curto_demais_nao_chama_llm(memoria):
    """'oi' / 'olá' fechado com DELETE: nem resumo, nem fatos, nem embedding."""

    memoria["doc"] = {"messages": _msgs(2), "resume": ""}

    await chat_service.encerrar_sessao("sessao-1", user_id="3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c")

    assert memoria["chamadas_resumo"] == []
    assert memoria["indexou"] == []


async def test_resumo_relevante_vai_pro_qdrant(memoria):
    memoria["doc"] = {"messages": _msgs(6), "resume": ""}

    await chat_service._atualizar_memoria("sessao-1", "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c")

    assert memoria["indexou"] == [("sessao-1", "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c", "resumo novo")]
    assert memoria["removeu"] == []


async def test_resumo_irrelevante_sai_do_qdrant(memoria):
    memoria["doc"] = {"messages": _msgs(6), "resume": ""}
    memoria["resumo"] = Resumo(resumo="Usuário só cumprimentou.", relevante=False)

    await chat_service._atualizar_memoria("sessao-1", "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c")

    assert memoria["indexou"] == []
    assert memoria["removeu"] == ["sessao-1"]
    # o resumo no Mongo continua salvo — `resumido_ate` avança mesmo sem embedding
    assert memoria["salvou"] == [("Usuário só cumprimentou.", "sessao-1", "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c", 6)]


async def test_qdrant_fora_do_ar_nao_desfaz_o_resumo(memoria, monkeypatch):
    memoria["doc"] = {"messages": _msgs(6), "resume": ""}

    async def _falha(*_):
        raise ConnectionError("qdrant fora")

    monkeypatch.setattr(chat_embeddings_repository, "salvar_resumo", _falha)

    await chat_service._atualizar_memoria("sessao-1", "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c")

    assert memoria["salvou"] == [("resumo novo", "sessao-1", "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c", 6)]
    # embedding não confirmado: fica pendente pro reconciliador
    assert memoria["indexado_ate"] == []


async def test_embedding_atrasado_e_refeito_sem_chamar_llm(memoria):
    """Resumo já salvo, Qdrant tinha falhado: a próxima passada só reindexa."""

    memoria["doc"] = {"messages": _msgs(6), "resume": "r salvo", "resumido_ate": 6,
                      "resume_relevante": True, "indexado_ate": 0}

    await chat_service._atualizar_memoria("sessao-1", "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c")

    assert memoria["chamadas_resumo"] == []
    assert memoria["indexou"] == [("sessao-1", "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c", "r salvo")]
    assert memoria["indexado_ate"] == [6]


async def test_resumo_indexado_marca_indexado_ate(memoria):
    memoria["doc"] = {"messages": _msgs(6), "resume": ""}

    await chat_service._atualizar_memoria("sessao-1", "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c")

    assert memoria["indexado_ate"] == [6]


async def test_reconciliador_processa_pendentes_globais(monkeypatch):
    async def _pendentes(minimo_mensagens, inativo_ha, limite):
        return [{"session_id": "s1", "user_id": "u1"}, {"session_id": "s2", "user_id": "u2"}], 7

    monkeypatch.setattr(chat_repository, "listar_pendentes_globais", _pendentes)

    feitos = []

    async def _atualizar_memoria(session_id, user_id):
        feitos.append((session_id, user_id))

    monkeypatch.setattr(chat_service, "_atualizar_memoria", _atualizar_memoria)

    await chat_service.reconciliar_memoria()

    assert feitos == [("s1", "u1"), ("s2", "u2")]
    assert chat_service_module.MEMORY_PENDING._value.get() == 7


async def test_reconciliador_espera_antes_de_repetir_chat_que_falhou(monkeypatch):
    """Chat que sempre falha (extração rejeitada, Qdrant fora) não pode gastar LLM a cada ciclo."""

    async def _pendentes(minimo_mensagens, inativo_ha, limite):
        return [{"session_id": "ruim", "user_id": "u1"}, {"session_id": "bom", "user_id": "u1"}], 2

    monkeypatch.setattr(chat_repository, "listar_pendentes_globais", _pendentes)
    monkeypatch.setattr(chat_service_module, "_falhou_em", {})

    tentativas = []

    async def _atualizar_memoria(session_id, user_id):
        tentativas.append(session_id)
        return session_id != "ruim"

    monkeypatch.setattr(chat_service, "_atualizar_memoria", _atualizar_memoria)

    await chat_service.reconciliar_memoria()
    await chat_service.reconciliar_memoria()

    assert tentativas == ["ruim", "bom", "bom"]  # "ruim" não volta no 2º ciclo

    chat_service_module._falhou_em["ruim"] -= chat_service_module._MEM.espera_apos_falha_s + 1
    await chat_service.reconciliar_memoria()

    assert tentativas[-2:] == ["ruim", "bom"]


async def test_stream_interrompido_ainda_grava_o_turno(monkeypatch):
    """Cliente fecha o SSE no meio: o gerador é fechado, mas o turno vai pro Mongo."""

    async def _executar_stream(*_):
        yield RunStarted()
        yield AnswerReady(content="resposta parcial")
        yield RunStarted()  # nunca consumido

    salvos = []

    async def _salvar(user_id, session_id, novas):
        salvos.append([m.content for m in novas])

    async def _talvez(*_):
        pass

    monkeypatch.setattr(runner, "executar_stream", _executar_stream)
    monkeypatch.setattr(chat_repository, "salvar_mensagens", _salvar)
    monkeypatch.setattr(chat_service, "_talvez_atualizar_memoria", _talvez)

    gerador = chat_service.stream_message("pergunta", "sessao-1", "u1", None)
    await anext(gerador)
    await anext(gerador)
    await gerador.aclose()
    await chat_service_module.drenar_tarefas(timeout=1)

    assert salvos == [["pergunta", "resposta parcial"]]


async def test_persistir_turno_tenta_de_novo_quando_mongo_falha(monkeypatch):
    tentativas = []

    async def _salvar(*_):
        tentativas.append(1)
        if len(tentativas) < 2:
            raise ConnectionError("mongo reiniciando")

    async def _talvez(*_):
        pass

    async def _sem_espera(_):
        pass

    monkeypatch.setattr(chat_repository, "salvar_mensagens", _salvar)
    monkeypatch.setattr(chat_service, "_talvez_atualizar_memoria", _talvez)
    monkeypatch.setattr(asyncio, "sleep", _sem_espera)

    await chat_service._persistir_turno("p", "r", "sessao-1", "u1", via="send")

    assert len(tentativas) == 2


async def test_atualizar_memoria_salva_fatos_quando_extracao_funciona(memoria):
    memoria["doc"] = {"messages": _msgs(4), "resume": ""}
    memoria["fatos"] = Fatos(alergias=["amendoim"])

    await chat_service._atualizar_memoria("sessao-1", "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c")

    assert memoria["fatos_salvos"] == [("3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c", Fatos(alergias=["amendoim"]))]


async def test_novo_chat_resume_os_pendentes_em_sequencia(monkeypatch):
    async def _pendentes(user_id, minimo_mensagens, limite):
        return ["antigo-1", "antigo-2"]

    monkeypatch.setattr(chat_repository, "listar_pendentes_de_resumo", _pendentes)

    resumidos = []

    async def _atualizar_memoria(session_id, user_id):
        resumidos.append((session_id, user_id))

    monkeypatch.setattr(chat_service, "_atualizar_memoria", _atualizar_memoria)

    await chat_service._resumir_pendentes("3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c")

    assert resumidos == [("antigo-1", "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c"), ("antigo-2", "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c")]


async def test_analisar_foto_usa_thread_id_unico_e_nao_salva_historico(monkeypatch):
    """Foto não é conversa: sem `salvar_mensagens`, `thread_id` descartável (não é o
    `session_id` de nenhum chat existente)."""

    chamadas = []

    async def _executar(conteudo, session_id, user_id, stock_id, imagem_b64=None):
        chamadas.append((conteudo, session_id, user_id, stock_id, imagem_b64))
        return "Você tem leite e ovos."

    descartadas = []

    async def _descartar(thread_id):
        descartadas.append(thread_id)

    salvou = []
    monkeypatch.setattr(runner, "executar", _executar)
    monkeypatch.setattr(runner, "descartar_thread", _descartar)
    monkeypatch.setattr(chat_repository, "salvar_mensagens", lambda *a, **kw: salvou.append(a))

    resposta = await chat_service.analisar_foto(user_id="3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c", stock_id=1, imagem=b"fake-jpeg-bytes")

    assert resposta == "Você tem leite e ovos."
    assert len(chamadas) == 1
    _, session_id, user_id, stock_id, imagem_b64 = chamadas[0]
    assert session_id.startswith("visao-3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c-")
    assert user_id == "3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c"
    assert stock_id == 1
    assert imagem_b64 == "ZmFrZS1qcGVnLWJ5dGVz"  # base64 de b"fake-jpeg-bytes"
    assert salvou == []
    # a thread descartável é apagada depois: análise avulsa não deixa checkpoint
    assert descartadas == [session_id]


async def test_analisar_foto_sem_resposta_devolve_mensagem_padrao(monkeypatch):
    async def _executar(*args, **kwargs):
        return None

    async def _descartar(thread_id):
        pass

    monkeypatch.setattr(runner, "executar", _executar)
    monkeypatch.setattr(runner, "descartar_thread", _descartar)

    resposta = await chat_service.analisar_foto(user_id="3f2b8c1e-5a4d-4e9b-9c7a-1d2e3f4a5b6c", stock_id=1, imagem=b"x")

    assert resposta == "Não consegui analisar a foto."


async def test_send_message_com_foto_manda_o_base64_pro_grafo_e_grava_so_o_texto(monkeypatch):
    recebido = {}

    async def _executar(conteudo, session_id, user_id, stock_id, **kwargs):
        recebido["kwargs"] = kwargs
        return "Vi leite."

    gravadas = []

    async def _salvar(user_id, session_id, novas):
        gravadas.extend(novas)

    async def _limite(user_id):
        return None

    monkeypatch.setattr(runner, "executar", _executar)
    monkeypatch.setattr(chat_repository, "salvar_mensagens", _salvar)
    monkeypatch.setattr(chat_service, "garantir_limite", _limite)

    resposta = await chat_service.send_message("e agora?", "chat-1", "u1", 1, imagem=b"fake-jpeg-bytes")

    assert resposta == "Vi leite."
    assert recebido["kwargs"] == {"imagem_b64": "ZmFrZS1qcGVnLWJ5dGVz"}
    assert [m.content for m in gravadas] == ["e agora?", "Vi leite."]  # a foto não vai pro histórico


async def test_send_message_sem_foto_nao_passa_imagem_ao_grafo(monkeypatch):
    recebido = {}

    async def _executar(conteudo, session_id, user_id, stock_id, **kwargs):
        recebido["kwargs"] = kwargs
        return "oi"

    async def _limite(user_id):
        return None

    async def _salvar(*a, **kw):
        return None

    monkeypatch.setattr(runner, "executar", _executar)
    monkeypatch.setattr(chat_repository, "salvar_mensagens", _salvar)
    monkeypatch.setattr(chat_service, "garantir_limite", _limite)

    await chat_service.send_message("oi", "chat-1", "u1", 1)

    assert recebido["kwargs"] == {}


def test_conversa_redige_pii_antes_de_ir_pro_llm():
    texto = chat_service_module._conversa([{"role": "user", "content": "meu cpf é 123.456.789-09"}])

    assert "123.456.789-09" not in texto
    assert "CPF OMITIDO" in texto


async def test_stream_sem_resposta_final_nao_grava_turno(monkeypatch):
    """Desconexão ou falha antes da resposta não vira "Sem resposta." na memória."""

    async def _executar_stream(*_):
        yield RunStarted()
        yield RunFailed(message="falhou")

    salvos = []

    async def _salvar(user_id, session_id, novas):
        salvos.append(novas)

    monkeypatch.setattr(runner, "executar_stream", _executar_stream)
    monkeypatch.setattr(chat_repository, "salvar_mensagens", _salvar)

    _ = [e async for e in chat_service.stream_message("pergunta", "sessao-1", "u1", None)]
    await chat_service_module.drenar_tarefas(timeout=1)

    assert salvos == []


@pytest.mark.parametrize("dono, erro", [(None, ChatNaoEncontrado), ("outro", ChatDeOutroUsuario), ("u1", None)])
async def test_validar_ownership_exige_chat_existente_e_do_usuario(monkeypatch, dono, erro):
    async def _buscar_dono(session_id):
        return dono

    monkeypatch.setattr(chat_repository, "buscar_dono_chat", _buscar_dono)

    if erro is None:
        await chat_service.validar_ownership("c1", "u1")
    else:
        with pytest.raises(erro):
            await chat_service.validar_ownership("c1", "u1")
