"""
`@especialista` monta o `EspecialistaUpdate` no lugar de cada nó: texto vira resposta e dados iguais,
`ConteudoEspecialista` separa os dois, e especialista nunca publica em `messages`.
"""

from frigus_ai.graph.names import ESTOQUE
from frigus_ai.graph.nodes.especialista import especialista
from frigus_ai.graph.state import ConteudoEspecialista


async def test_texto_vira_resposta_e_dados_iguais():
    @especialista(ESTOQUE)
    async def no(estado, runtime):
        return "tem leite"

    update = await no({}, None)

    assert update == {
        "agentes_chamados": [ESTOQUE],
        "dados_especialistas": [{"agente": ESTOQUE, "resposta": "tem leite", "dados": "tem leite"}],
    }
    assert "messages" not in update


async def test_conteudo_separa_resposta_de_dados():
    @especialista(ESTOQUE)
    async def no(estado, runtime):
        return ConteudoEspecialista(resposta="fora do ar", dados="")

    [resultado] = (await no({}, None))["dados_especialistas"]

    assert (resultado["resposta"], resultado["dados"]) == ("fora do ar", "")
