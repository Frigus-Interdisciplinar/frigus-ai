"""
Orquestração de fatos/resumo em `ChatService`: atualizados periodicamente durante a
conversa (`_talvez_atualizar_memoria`, a cada N mensagens), não só quando a sessão
fecha — sessão nunca fechada não pode ficar sem nada. `encerrar_sessao` só cobre o
rabo que o ciclo periódico ainda não alcançou. Tudo mockado (repository/user_service);
a query em si já tem teste próprio em tests/repositories/test_chat_repository.py.
"""

from frigus_ai.repositories import chat_repository
from frigus_ai.schemas.models import Fatos
from frigus_ai.services import chat_service as chat_service_module
from frigus_ai.services import runner
from frigus_ai.services.chat_service import service as chat_service
from frigus_ai.services.user_service import user_service


async def test_encerrar_sessao_no_multiplo_do_intervalo_nao_repete_atualizacao(monkeypatch):
    """Ciclo periódico já cobriu esse total — rodar de novo repetiria a mesma
    chamada de LLM à toa."""

    async def _contar(session_id, user_id):
        return 20  # múltiplo de _INTERVALO_ATUALIZACAO_MEMORIA (10)

    monkeypatch.setattr(chat_repository, "contar_mensagens", _contar)

    chamou = []
    monkeypatch.setattr(chat_service, "_atualizar_memoria", lambda s, u: chamou.append((s, u)))

    await chat_service.encerrar_sessao("sessao-1", user_id=7)

    assert chamou == []


async def test_encerrar_sessao_com_rabo_cobre_o_que_falta(monkeypatch):
    async def _contar(session_id, user_id):
        return 23  # 3 mensagens além do último múltiplo de 10

    monkeypatch.setattr(chat_repository, "contar_mensagens", _contar)

    chamou = []

    async def _atualizar_memoria(session_id, user_id):
        chamou.append((session_id, user_id))

    monkeypatch.setattr(chat_service, "_atualizar_memoria", _atualizar_memoria)

    await chat_service.encerrar_sessao("sessao-1", user_id=7)

    assert chamou == [("sessao-1", 7)]


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


async def test_atualizar_memoria_ignora_fatos_indisponivel_mas_salva_resumo(monkeypatch):
    async def _doc(session_id, user_id):
        return {
            "messages": [{"role": "human", "content": "sou alérgico a amendoim"}],
            "resume": "resumo antigo",
        }

    async def _buscar_fatos(user_id):
        return Fatos()

    monkeypatch.setattr(chat_repository, "buscar_documento_completo", _doc)
    monkeypatch.setattr(user_service, "buscar_fatos", _buscar_fatos)
    monkeypatch.setattr(chat_service_module, "_extrair_fatos", lambda msgs, atuais: None)
    monkeypatch.setattr(chat_service_module, "_atualizar_resumo", lambda atual, msgs: "resumo novo")

    chamou_fatos = []

    async def _atualizar_fatos_por_extracao(user_id, extraidos):
        chamou_fatos.append((user_id, extraidos))

    monkeypatch.setattr(user_service, "atualizar_fatos_por_extracao", _atualizar_fatos_por_extracao)

    salvou_resumo = []

    async def _salvar_resumo(resumo, session_id, user_id):
        salvou_resumo.append((resumo, session_id, user_id))

    monkeypatch.setattr(chat_repository, "salvar_resumo", _salvar_resumo)

    await chat_service._atualizar_memoria("sessao-1", 7)

    assert chamou_fatos == []
    assert salvou_resumo == [("resumo novo", "sessao-1", 7)]


async def test_atualizar_memoria_salva_fatos_quando_extracao_funciona(monkeypatch):
    async def _doc(session_id, user_id):
        return {"messages": [{"role": "human", "content": "sou alérgico a amendoim"}], "resume": ""}

    async def _buscar_fatos(user_id):
        return Fatos()

    extraidos = Fatos(alergias=["amendoim"])

    monkeypatch.setattr(chat_repository, "buscar_documento_completo", _doc)
    monkeypatch.setattr(user_service, "buscar_fatos", _buscar_fatos)
    monkeypatch.setattr(chat_service_module, "_extrair_fatos", lambda msgs, atuais: extraidos)
    monkeypatch.setattr(chat_service_module, "_atualizar_resumo", lambda atual, msgs: "x")
    monkeypatch.setattr(chat_repository, "salvar_resumo", lambda *a, **kw: None)

    chamou = []

    async def _atualizar(user_id, fatos):
        chamou.append((user_id, fatos))

    monkeypatch.setattr(user_service, "atualizar_fatos_por_extracao", _atualizar)

    await chat_service._atualizar_memoria("sessao-1", 7)

    assert chamou == [(7, extraidos)]


async def test_atualizar_memoria_resumo_recebe_so_a_janela_recente(monkeypatch):
    """Resumo é incremental: recebe o resumo já salvo + só a janela recente de
    mensagens, não a conversa inteira — é essa a economia de token sobre o
    'full pass' antigo em `encerrar_sessao`."""

    async def _doc(session_id, user_id):
        return {
            "messages": [{"role": "human", "content": f"msg {i}"} for i in range(15)],
            "resume": "resumo salvo",
        }

    async def _buscar_fatos(user_id):
        return Fatos()

    monkeypatch.setattr(chat_repository, "buscar_documento_completo", _doc)
    monkeypatch.setattr(user_service, "buscar_fatos", _buscar_fatos)
    monkeypatch.setattr(chat_service_module, "_extrair_fatos", lambda msgs, atuais: None)

    chamadas = []

    def _atualizar_resumo(resumo_atual, mensagens_recentes):
        chamadas.append((resumo_atual, mensagens_recentes))
        return "resumo novo"

    monkeypatch.setattr(chat_service_module, "_atualizar_resumo", _atualizar_resumo)

    salvou = []
    monkeypatch.setattr(
        chat_repository, "salvar_resumo", lambda resumo, session_id, user_id: salvou.append(resumo)
    )

    await chat_service._atualizar_memoria("sessao-1", 7)

    assert len(chamadas) == 1
    resumo_atual, recentes = chamadas[0]
    assert resumo_atual == "resumo salvo"
    assert len(recentes) == 10  # só a janela (_INTERVALO_ATUALIZACAO_MEMORIA), não as 15
    assert salvou == ["resumo novo"]


async def test_analisar_foto_usa_thread_id_unico_e_nao_salva_historico(monkeypatch):
    """Foto não é conversa: sem `salvar_mensagens`, `thread_id` descartável (não é o
    `session_id` de nenhum chat existente)."""

    chamadas = []

    async def _executar(conteudo, session_id, user_id, stock_id, imagem_b64=None):
        chamadas.append((conteudo, session_id, user_id, stock_id, imagem_b64))
        return "Você tem leite e ovos."

    salvou = []
    monkeypatch.setattr(runner, "executar", _executar)
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


async def test_analisar_foto_sem_resposta_devolve_mensagem_padrao(monkeypatch):
    async def _executar(*args, **kwargs):
        return None

    monkeypatch.setattr(runner, "executar", _executar)

    resposta = await chat_service.analisar_foto(user_id=7, stock_id=1, imagem=b"x")

    assert resposta == "Não consegui analisar a foto."
