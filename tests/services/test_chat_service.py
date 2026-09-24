"""
Orquestração de fatos/resumo em `ChatService`: atualizados periodicamente durante a
conversa (`_talvez_atualizar_memoria`, a cada N mensagens), no fechamento da sessão e
quando o usuário abre um chat novo (`_resumir_pendentes`) — chat abandonado não pode
ficar sem resumo. Só o que o resumo ainda não cobre (`resumido_ate`) vai pro LLM, chat
curto demais não gasta LLM, e só resumo `relevante` vira embedding. Tudo mockado
(repositories/user_service); a query em si tem teste em tests/repositories/.
"""

import pytest

from frigus_ai.repositories import chat_embeddings_repository, chat_repository
from frigus_ai.schemas.models import Fatos, Resumo
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
                "removeu": [], "fatos_salvos": []}

    async def _doc(session_id, user_id):
        return registro["doc"]

    async def _buscar_fatos(user_id):
        return Fatos()

    def _atualizar_resumo(atual, msgs):
        registro["chamadas_resumo"].append((atual, msgs))
        return registro["resumo"]

    async def _salvar_resumo(resumo, session_id, user_id, resumido_ate):
        registro["salvou"].append((resumo, session_id, user_id, resumido_ate))

    async def _indexar(session_id, user_id, resumo):
        registro["indexou"].append((session_id, user_id, resumo))

    async def _remover(session_id):
        registro["removeu"].append(session_id)

    async def _atualizar_fatos(user_id, fatos):
        registro["fatos_salvos"].append((user_id, fatos))

    monkeypatch.setattr(chat_repository, "buscar_documento_completo", _doc)
    monkeypatch.setattr(chat_repository, "salvar_resumo", _salvar_resumo)
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

    await chat_service._talvez_atualizar_memoria("sessao-1", 7)

    assert len(disparadas) == 1
    disparadas[0].close()  # não executa o corpo — só confirma que foi agendado


async def test_talvez_atualizar_memoria_nao_dispara_fora_do_intervalo(monkeypatch):
    async def _contar(session_id, user_id):
        return 7

    monkeypatch.setattr(chat_repository, "contar_mensagens", _contar)

    disparadas = []
    monkeypatch.setattr(chat_service_module, "_disparar_em_segundo_plano", disparadas.append)

    await chat_service._talvez_atualizar_memoria("sessao-1", 7)

    assert disparadas == []


async def test_resumo_recebe_so_o_que_ainda_nao_foi_resumido(memoria):
    memoria["doc"] = {"messages": _msgs(15), "resume": "resumo salvo", "resumido_ate": 10}

    await chat_service._atualizar_memoria("sessao-1", 7)

    [(resumo_atual, recentes)] = memoria["chamadas_resumo"]
    assert resumo_atual == "resumo salvo"
    assert [m["content"] for m in recentes] == [f"msg {i}" for i in range(10, 15)]
    assert memoria["salvou"] == [("resumo novo", "sessao-1", 7, 15)]


async def test_chat_ja_resumido_nao_chama_llm(memoria):
    """Fecha a sessão logo depois do ciclo periódico: nada novo, nada a fazer."""

    memoria["doc"] = {"messages": _msgs(10), "resume": "r", "resumido_ate": 10}

    await chat_service.encerrar_sessao("sessao-1", user_id=7)

    assert memoria["chamadas_resumo"] == []
    assert memoria["salvou"] == []


async def test_chat_curto_demais_nao_chama_llm(memoria):
    """'oi' / 'olá' fechado com DELETE: nem resumo, nem fatos, nem embedding."""

    memoria["doc"] = {"messages": _msgs(2), "resume": ""}

    await chat_service.encerrar_sessao("sessao-1", user_id=7)

    assert memoria["chamadas_resumo"] == []
    assert memoria["indexou"] == []


async def test_resumo_relevante_vai_pro_qdrant(memoria):
    memoria["doc"] = {"messages": _msgs(6), "resume": ""}

    await chat_service._atualizar_memoria("sessao-1", 7)

    assert memoria["indexou"] == [("sessao-1", 7, "resumo novo")]
    assert memoria["removeu"] == []


async def test_resumo_irrelevante_sai_do_qdrant(memoria):
    memoria["doc"] = {"messages": _msgs(6), "resume": ""}
    memoria["resumo"] = Resumo(resumo="Usuário só cumprimentou.", relevante=False)

    await chat_service._atualizar_memoria("sessao-1", 7)

    assert memoria["indexou"] == []
    assert memoria["removeu"] == ["sessao-1"]
    # o resumo no Mongo continua salvo — `resumido_ate` avança mesmo sem embedding
    assert memoria["salvou"] == [("Usuário só cumprimentou.", "sessao-1", 7, 6)]


async def test_qdrant_fora_do_ar_nao_desfaz_o_resumo(memoria, monkeypatch):
    memoria["doc"] = {"messages": _msgs(6), "resume": ""}

    async def _falha(*_):
        raise ConnectionError("qdrant fora")

    monkeypatch.setattr(chat_embeddings_repository, "salvar_resumo", _falha)

    await chat_service._atualizar_memoria("sessao-1", 7)

    assert memoria["salvou"] == [("resumo novo", "sessao-1", 7, 6)]


async def test_atualizar_memoria_salva_fatos_quando_extracao_funciona(memoria):
    memoria["doc"] = {"messages": _msgs(4), "resume": ""}
    memoria["fatos"] = Fatos(alergias=["amendoim"])

    await chat_service._atualizar_memoria("sessao-1", 7)

    assert memoria["fatos_salvos"] == [(7, Fatos(alergias=["amendoim"]))]


async def test_novo_chat_resume_os_pendentes_em_sequencia(monkeypatch):
    async def _pendentes(user_id, minimo_mensagens, limite):
        return ["antigo-1", "antigo-2"]

    monkeypatch.setattr(chat_repository, "listar_pendentes_de_resumo", _pendentes)

    resumidos = []

    async def _atualizar_memoria(session_id, user_id):
        resumidos.append((session_id, user_id))

    monkeypatch.setattr(chat_service, "_atualizar_memoria", _atualizar_memoria)

    await chat_service._resumir_pendentes(7)

    assert resumidos == [("antigo-1", 7), ("antigo-2", 7)]


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

    resposta = await chat_service.analisar_foto(user_id=7, stock_id=1, imagem=b"fake-jpeg-bytes")

    assert resposta == "Você tem leite e ovos."
    assert len(chamadas) == 1
    _, session_id, user_id, stock_id, imagem_b64 = chamadas[0]
    assert session_id.startswith("visao-7-")
    assert user_id == 7
    assert stock_id == 1
    assert imagem_b64 == "ZmFrZS1qcGVnLWJ5dGVz"  # base64 de b"fake-jpeg-bytes"
    assert salvou == []
    # a thread descartável é apagada depois (o checkpoint guardava o base64 pra sempre)
    assert descartadas == [session_id]


async def test_analisar_foto_sem_resposta_devolve_mensagem_padrao(monkeypatch):
    async def _executar(*args, **kwargs):
        return None

    async def _descartar(thread_id):
        pass

    monkeypatch.setattr(runner, "executar", _executar)
    monkeypatch.setattr(runner, "descartar_thread", _descartar)

    resposta = await chat_service.analisar_foto(user_id=7, stock_id=1, imagem=b"x")

    assert resposta == "Não consegui analisar a foto."
