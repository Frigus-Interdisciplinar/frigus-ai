"""
Nó de visão: identifica itens numa foto de geladeira/freezer/despensa. Diferente dos
outros nós, não usa `responder()` (agente + tools) — é uma chamada de visão direta,
sem tool nenhuma, mas devolve o mesmo `EspecialistaUpdate` que Estoque/Compras/
Financeiro, pro Orquestrador reescrever em linguagem natural.

`category`/`storage_place` reaproveitam os `Literal` de `graph/tools/estoque/schemas.py`
— são os MESMOS valores que `POST /stock/items` aceita. Como o `with_structured_output`
vira function-calling/JSON-schema pro provider, o Gemini fica proibido de emitir um
valor fora da lista (não é só uma checagem depois, é uma restrição na própria geração).
"""

from langchain_core.messages import HumanMessage

from frigus_ai.exceptions import FalhaNoAgente
from frigus_ai.graph.llm import llm_visao
from frigus_ai.graph.names import VISAO
from frigus_ai.graph.prompts import load_prompt
from frigus_ai.graph.state import Estado, Route, VisaoUpdate
from frigus_ai.observability.metrics import medir_node


@medir_node(VISAO)
async def no_visao(estado: Estado) -> VisaoUpdate:
    if llm_visao is None:
        raise FalhaNoAgente("Modelo de visão não configurado (GEMINI_API_KEY ausente).")

    b64 = estado["imagem_b64"]
    prompt = load_prompt("visao")

    # Retry do Juiz: sem o feedback, a segunda chamada seria idêntica à reprovada.
    if feedback := estado.get("feedback_juiz"):
        prompt += f"\n\n[REVISÃO SOLICITADA PELO JUIZ] {feedback}"

    msg = HumanMessage(content=[
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
    ])

    inventario = await llm_visao.ainvoke([msg])

    return VisaoUpdate(
        agentes_chamados=[VISAO],
        rota=Route.VISAO,
        resposta_especialista=inventario.model_dump_json(),
        dados_especialista=inventario.model_dump_json(),
    )


__all__ = ["no_visao"]
