import re

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage

from frigus_ai.evals.metrics import medir_node
from frigus_ai.graph.llm import llm_juiz
from frigus_ai.graph.names import JUIZ
from frigus_ai.graph.nodes.contexto import perguntar
from frigus_ai.graph.prompts import load_prompt, load_sections
from frigus_ai.graph.state import Estado, JuizUpdate
from frigus_ai.logging import Logging

logger = Logging.get_logger(__name__)

# Quantas vezes o Juiz manda o especialista tentar de novo antes de deixar passar
# mesmo reprovado (mesmo princípio do guardrail de saída: nunca trava o usuário).
MAX_TENTATIVAS = 2

APROVADO = "APROVADO"
REPROVADO = "REPROVADO"

_TEMPLATE = load_sections("juiz.md")["template"]


def _mensagens(estado: Estado) -> list[AnyMessage]:
    prompt = _TEMPLATE.format(
        pergunta_original=estado.get("pergunta_original", ""),
        dados_disponiveis=estado.get("dados_especialista", ""),
        resposta_gerada=estado.get("resposta_especialista", ""),
    )

    return [
        SystemMessage(content=load_prompt("juiz")),  # load_prompt carrega a data do turno
        HumanMessage(content=prompt),
    ]


def _extrair_veredito(texto: str) -> tuple[str, str]:
    """Na dúvida aprova: formato inesperado não pode travar a resposta do usuário."""

    veredito_match = re.search(rf"VEREDITO:\s*({APROVADO}|{REPROVADO})", texto, re.IGNORECASE)
    justificativa_match = re.search(r"JUSTIFICATIVA:\s*(.+)", texto)

    veredito = veredito_match.group(1).upper() if veredito_match else APROVADO
    justificativa = justificativa_match.group(1).strip() if justificativa_match else ""

    return veredito, justificativa


def _logar(veredito: str, justificativa: str, tentativas: int, repetir: bool) -> None:
    if repetir:
        logger.warning(
            "Juiz REPROVOU (tentativa %s/%s): %s", tentativas + 1, MAX_TENTATIVAS, justificativa
        )
    elif veredito == REPROVADO:
        logger.warning(
            "Juiz REPROVOU mas as tentativas se esgotaram — seguindo mesmo assim: %s", justificativa
        )
    else:
        logger.info("Juiz APROVOU: %s", justificativa)


@medir_node(JUIZ)
async def no_juiz(estado: Estado) -> JuizUpdate:
    tentativas = estado.get("tentativas_juiz", 0)

    veredito, justificativa = _extrair_veredito(await perguntar(llm_juiz, _mensagens(estado)))
    repetir = veredito == REPROVADO and tentativas < MAX_TENTATIVAS

    _logar(veredito, justificativa, tentativas, repetir)

    return JuizUpdate(
        agentes_chamados=[JUIZ],
        veredito_juiz=veredito,
        justificativa_juiz=justificativa,
        # feedback_juiz preenchido é o sinal que `decidir_apos_juiz` lê pra devolver
        # a resposta ao especialista de origem; vazio segue pro guardrail de saída.
        feedback_juiz=justificativa if repetir else "",
        tentativas_juiz=tentativas + 1 if repetir else tentativas,
    )


__all__ = ["MAX_TENTATIVAS", "no_juiz"]
