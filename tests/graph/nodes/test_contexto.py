"""
Poda do histórico: sem ela o canal `messages` cresce ~3 mensagens por turno para sempre —
o checkpoint no Mongo incha e todo turno relê o histórico inteiro pro contexto do LLM
(custo em token, não só memória).
"""

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langgraph.graph.message import add_messages

from frigus_ai.graph.nodes.contexto import MAX_MENSAGENS, podar_historico


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
