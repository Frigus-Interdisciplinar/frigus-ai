from typing import Literal

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from frigus_ai.graph.llm import llm_juiz
from frigus_ai.graph.names import JUIZ
from frigus_ai.graph.prompts import load_prompt, load_sections
from frigus_ai.graph.state import Estado, JuizUpdate
from frigus_ai.infra.logging import Logging
from frigus_ai.observability import medir_node
from frigus_ai.settings import settings

logger = Logging.get_logger(__name__)

# Quantas vezes o Juiz manda o especialista tentar de novo antes de deixar passar
# mesmo reprovado (mesmo princípio do guardrail de saída: nunca trava o usuário). Falha na
# chamada ou saída fora do schema também aprova.
MAX_TENTATIVAS = settings.llm.max_tentativas_juiz

APROVADO = "APROVADO"
REPROVADO = "REPROVADO"


class VereditoJuiz(BaseModel):
    """Saída estruturada do Juiz."""

    veredito: Literal["APROVADO", "REPROVADO"]
    justificativa: str


llm_avaliador = llm_juiz.with_structured_output(VereditoJuiz) if llm_juiz else None

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

    try:
        avaliacao = await llm_avaliador.ainvoke(_mensagens(estado))
        if not isinstance(avaliacao, VereditoJuiz):
            raise TypeError(f"esperava VereditoJuiz, veio {type(avaliacao).__name__}")
        veredito, justificativa = avaliacao.veredito, avaliacao.justificativa.strip()
    except Exception as e:
        logger.warning("Falha ao invocar Juiz (%s) — aprovando por segurança: %s", type(e).__name__, e)
        veredito, justificativa = APROVADO, "Aprovado por fallback após falha na avaliação"

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
