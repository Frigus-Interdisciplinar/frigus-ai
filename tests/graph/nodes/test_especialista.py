"""
`@especialista` monta o `EspecialistaUpdate` no lugar de cada nó: texto vira resposta e dados iguais,
`ConteudoEspecialista` separa os dois, e especialista nunca publica em `messages`.
"""

from frigus_ai.graph.names import ESTOQUE, VISAO
from frigus_ai.graph.nodes.especialista import especialista
from frigus_ai.graph.state import ConteudoEspecialista, Route


async def test_texto_vira_resposta_e_dados_iguais():
    @especialista(ESTOQUE)
    async def no(estado, runtime):
        return "tem leite"

    update = await no({}, None)

    assert update == {
        "agentes_chamados": [ESTOQUE],
        "resposta_especialista": "tem leite",
        "dados_especialista": "tem leite",
    }
    assert "messages" not in update


async def test_conteudo_separa_resposta_de_dados():
    @especialista(ESTOQUE)
    async def no(estado, runtime):
        return ConteudoEspecialista(resposta="fora do ar", dados="")

    update = await no({}, None)

    assert (update["resposta_especialista"], update["dados_especialista"]) == ("fora do ar", "")


async def test_rota_so_aparece_quando_pedida():
    @especialista(VISAO, rota=Route.VISAO)
    async def no(estado, runtime):
        return "{}"

    assert (await no({}, None))["rota"] == Route.VISAO
