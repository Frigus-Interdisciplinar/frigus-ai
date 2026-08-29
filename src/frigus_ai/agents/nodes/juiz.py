import re

from config.logging import get_logger
from frigus_ai.agents.nodes.names import Node
from frigus_ai.agents.prompts.loader import load_prompt, load_sections
from frigus_ai.graph.llm import llm_juiz
from frigus_ai.graph.state import Estado

logger = get_logger(__name__)

# Quantas vezes o Juiz manda o especialista tentar de novo antes de deixar passar
# mesmo reprovado (mesmo princípio do guardrail de saída: nunca trava o usuário).
MAX_TENTATIVAS = 2

_TEMPLATE = load_sections("juiz.md")["template"]


def _extrair_veredito(texto: str) -> tuple[str, str]:
    veredito_match = re.search(r"VEREDITO:\s*(APROVADO|REPROVADO)", texto, re.IGNORECASE)
    justificativa_match = re.search(r"JUSTIFICATIVA:\s*(.+)", texto)

    veredito = veredito_match.group(1).upper() if veredito_match else "APROVADO"
    justificativa = justificativa_match.group(1).strip() if justificativa_match else ""

    return veredito, justificativa


async def no_juiz(estado: Estado) -> dict:

    tentativas = estado.get("tentativas_juiz", 0)

    prompt = _TEMPLATE.format(
        pergunta_original=estado.get("pergunta_original", ""),
        dados_disponiveis=estado.get("dados_especialista", ""),
        resposta_gerada=estado.get("resposta_especialista", ""),
    )

    resultado = await llm_juiz.ainvoke([
        {"role": "system", "content": load_prompt("juiz")},  # load_prompt carrega a data do turno
        {"role": "human", "content": prompt},
    ])
    saida = resultado.content

    veredito, justificativa = _extrair_veredito(saida)

    if veredito == "REPROVADO" and tentativas < MAX_TENTATIVAS:
        logger.warning("Juiz REPROVOU (tentativa %s/%s): %s", tentativas + 1, MAX_TENTATIVAS, justificativa)
        return {
            "agentes_chamados":   [Node.JUIZ],
            "veredito_juiz":      veredito,
            "justificativa_juiz": justificativa,
            "feedback_juiz":      justificativa,
            "tentativas_juiz":    tentativas + 1,
        }

    if veredito == "REPROVADO":
        logger.warning("Juiz REPROVOU mas as tentativas se esgotaram — seguindo mesmo assim: %s", justificativa)
    else:
        logger.info("Juiz APROVOU: %s", justificativa)

    return {
        "agentes_chamados":   [Node.JUIZ],
        "veredito_juiz":      veredito,
        "justificativa_juiz": justificativa,
        "feedback_juiz":      "",
    }


__all__ = ["MAX_TENTATIVAS", "no_juiz"]
