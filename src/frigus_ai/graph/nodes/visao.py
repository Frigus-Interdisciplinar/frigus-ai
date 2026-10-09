"""
Nó de visão: identifica itens numa foto de geladeira/freezer/despensa. Diferente dos
outros nós, não usa `responder()` (agente + tools) — é uma chamada de visão direta,
sem tool nenhuma, mas devolve o mesmo contrato (`@especialista`) que Estoque/Compras/
Financeiro, pro Orquestrador reescrever em linguagem natural.

`category`/`storage_place` reaproveitam os `Literal` de `graph/tools/estoque/schemas.py`
— são os MESMOS valores que `POST /stock/items` aceita. Como o `with_structured_output`
vira function-calling/JSON-schema pro provider, o Gemini fica proibido de emitir um
valor fora da lista (não é só uma checagem depois, é uma restrição na própria geração).
"""

from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime

from frigus_ai.domain.errors import FalhaNoAgente
from frigus_ai.graph.llm import llm_visao
from frigus_ai.graph.names import VISAO
from frigus_ai.graph.nodes.contexto import revisao_do_juiz
from frigus_ai.graph.nodes.especialista import especialista
from frigus_ai.graph.prompts import load_prompt
from frigus_ai.graph.state import ContextoPrompt, Estado, Route


@especialista(VISAO, rota=Route.VISAO)
async def no_visao(estado: Estado, runtime: Runtime[ContextoPrompt]) -> str:
    if llm_visao is None:
        raise FalhaNoAgente("Modelo de visão não configurado (GEMINI_API_KEY ausente).")

    b64 = estado["imagem_b64"]
    prompt = load_prompt("visao")

    # Retry do Juiz: sem o feedback, a segunda chamada seria idêntica à reprovada.
    if revisao := revisao_do_juiz(estado):
        prompt += f"\n\n{revisao}"

    msg = HumanMessage(content=[
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
    ])

    inventario = await llm_visao.ainvoke([msg])

    return inventario.model_dump_json()


__all__ = ["no_visao"]
