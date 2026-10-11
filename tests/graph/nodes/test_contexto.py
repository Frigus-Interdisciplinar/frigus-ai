"""
Poda do histórico: sem ela o canal `messages` cresce ~3 mensagens por turno para sempre —
o checkpoint no Mongo incha e todo turno relê o histórico inteiro pro contexto do LLM
(custo em token, não só memória).
"""

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langgraph.graph.message import add_messages

from frigus_ai.graph.nodes.contexto import (
    MAX_MENSAGENS,
    mensagens_do_turno,
    podar_historico,
    revisao_do_juiz,
)


def _historico(n: int) -> list:
    return [
        HumanMessage(id=f"m{i}", content=f"msg {i}") if i % 2 == 0
        else AIMessage(id=f"m{i}", content=f"msg {i}")
        for i in range(n)
    ]


def test_nao_poda_enquanto_cabe():
    assert podar_historico(_historico(MAX_MENSAGENS)) == []


def test_remove_so_o_excedente_mais_antigo():
    poda = podar_historico(_historico(MAX_MENSAGENS + 4))

    assert len(poda) == 4
    assert all(isinstance(m, RemoveMessage) for m in poda)
    assert [m.id for m in poda] == ["m0", "m1", "m2", "m3"]


def test_reducer_aplica_a_poda_e_estabiliza_o_tamanho():
    """O que importa de verdade: passar a poda pelo `add_messages` encurta mesmo."""

    historico = _historico(MAX_MENSAGENS + 10)
    resultado = add_messages(historico, podar_historico(historico))

    assert len(resultado) == MAX_MENSAGENS
    # Mantém as mais recentes, descarta as mais antigas.
    assert resultado[0].id == "m10"
    assert resultado[-1].id == f"m{MAX_MENSAGENS + 9}"


def test_mensagem_sem_id_e_ignorada():
    """RemoveMessage precisa de id; sem isso não há o que remover."""

    historico = [HumanMessage(content="sem id") for _ in range(MAX_MENSAGENS + 3)]

    assert podar_historico(historico) == []


def test_toolmessage_no_estado_desativa_a_poda():
    from langchain_core.messages import ToolMessage

    historico = [*_historico(MAX_MENSAGENS + 4), ToolMessage(content="x", tool_call_id="t1")]

    assert podar_historico(historico) == []


def test_corte_no_meio_de_uma_interacao_avanca_ate_a_proxima_pergunta():
    """Excedente ímpar cairia numa resposta: o histórico não pode começar sem a pergunta dela."""

    historico = _historico(MAX_MENSAGENS + 3)  # corte em m3, que é uma resposta (AI)
    resultado = add_messages(historico, podar_historico(historico))

    assert isinstance(resultado[0], HumanMessage)
    assert resultado[0].id == "m4"


def test_sem_pergunta_depois_do_corte_preserva_o_historico():
    historico = [HumanMessage(id="m0", content="oi")] + [
        AIMessage(id=f"m{i}", content="resposta") for i in range(1, MAX_MENSAGENS + 4)
    ]

    assert podar_historico(historico) == []


def test_mensagens_do_turno_junta_historico_e_pedido_de_revisao_do_juiz():
    estado = {"messages": _historico(2), "feedback_juiz": "faltou a validade"}

    mensagens = mensagens_do_turno(estado)

    assert [m.content for m in mensagens[:2]] == ["msg 0", "msg 1"]
    assert mensagens[-1].content == "[REVISÃO SOLICITADA PELO JUIZ] faltou a validade"
    assert revisao_do_juiz({"messages": []}) is None
    assert len(mensagens_do_turno({"messages": _historico(2)})) == 2


class _AgenteFake:
    def __init__(self, mensagens):
        self._mensagens = mensagens

    async def ainvoke(self, _entrada, context=None):
        return {"messages": self._mensagens}


async def test_responder_com_evidencias_separa_retorno_das_tools_da_resposta():
    from langchain_core.messages import AIMessage, ToolMessage

    from frigus_ai.graph.nodes.contexto import responder_com_evidencias

    agente = _AgenteFake(
        [
            ToolMessage(content='[{"nome": "leite"}]', name="listar_estoque", tool_call_id="1"),
            AIMessage(content="Você tem leite."),
        ]
    )

    resposta, evidencias = await responder_com_evidencias(agente, [])

    assert resposta == "Você tem leite."
    assert evidencias == 'listar_estoque:\n[{"nome": "leite"}]'
    assert await responder_com_evidencias(_AgenteFake([AIMessage(content="oi")]), []) == ("oi", "")
