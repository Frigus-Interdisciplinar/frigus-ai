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

import json

from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime

from frigus_ai.domain.errors import FalhaNoAgente
from frigus_ai.graph.llm import llm_visao
from frigus_ai.graph.names import VISAO
from frigus_ai.graph.nodes.contexto import revisao_do_juiz
from frigus_ai.graph.nodes.especialista import especialista
from frigus_ai.graph.prompts import load_prompt
from frigus_ai.graph.state import ContextoPrompt, Estado, ItemIdentificado
from frigus_ai.infra.llm import jev
from frigus_ai.infra.llm.jev.schemas import PerguntaPredicado
from frigus_ai.infra.logging import Logging
from frigus_ai.settings import settings

logger = Logging.get_logger(__name__)


async def _itens_incertos(b64: str, itens: list[ItemIdentificado]) -> list[str]:
    """Pergunta, pra cada item, se ele aparece na foto: o Juiz só vê o inventário, não a imagem, então
    é aqui que um item inventado pelo Gemini aparece. Sem o gateway, ou se ele falhar, ninguém é
    marcado — o usuário confere a lista de qualquer jeito."""

    if not itens or not jev.disponivel():
        return []

    try:
        decisoes = await jev.decidir(
            "visao",
            "Foto de geladeira, freezer ou despensa.",
            [
                PerguntaPredicado(
                    name=f"item_{i}", instructions=f"O item «{item.product_name}» aparece na foto?"
                )
                for i, item in enumerate(itens)
            ],
            imagem_b64=b64,
        )
    except Exception as e:
        logger.warning("Verificação dos itens da foto falhou, seguindo sem ela: %s", e)
        return []

    minimo = settings.llm.confianca_minima_item_visao
    return [item.product_name for i, item in enumerate(itens) if decisoes.probabilidade(f"item_{i}") < minimo]


@especialista(VISAO)
async def no_visao(estado: Estado, runtime: Runtime[ContextoPrompt]) -> str:
    if llm_visao is None:
        raise FalhaNoAgente("Modelo de visão não configurado (GEMINI_API_KEY ausente).")

    if not (b64 := runtime.context.imagem_b64):
        raise FalhaNoAgente("Turno de foto sem imagem no contexto.")

    prompt = load_prompt("visao")

    # Retry do Juiz: sem o feedback, a segunda chamada seria idêntica à reprovada.
    if revisao := revisao_do_juiz(estado):
        prompt += f"\n\n{revisao}"

    msg = HumanMessage(content=[
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
    ])

    inventario = await llm_visao.ainvoke([msg])

    saida = inventario.model_dump(mode="json")
    if incertos := await _itens_incertos(b64, inventario.items):
        # `esclarecer` o Orquestrador já transforma em pergunta pro usuário.
        saida["esclarecer"] = f"Não tenho certeza de que estes itens aparecem na foto: {', '.join(incertos)}. Confirme antes de cadastrar."

    return json.dumps(saida, ensure_ascii=False)


__all__ = ["no_visao"]
