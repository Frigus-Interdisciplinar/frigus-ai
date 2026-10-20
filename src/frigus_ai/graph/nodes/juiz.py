from enum import StrEnum
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from frigus_ai.graph.llm import estruturado, llm_juiz, llm_luna, llm_rapido
from frigus_ai.graph.names import JUIZ
from frigus_ai.graph.prompts import load_prompt, load_sections
from frigus_ai.graph.state import Estado, JuizUpdate
from frigus_ai.infra.llm import jev
from frigus_ai.infra.llm.jev.schemas import PerguntaEscolha, PerguntaPredicado
from frigus_ai.infra.logging import Logging
from frigus_ai.settings import settings
from frigus_ai.telemetry import medir_node

logger = Logging.get_logger(__name__)

# Quantas vezes o Juiz manda o orquestrador reescrever antes de deixar passar
# mesmo reprovado (mesmo princípio do guardrail de saída: nunca trava o usuário). Falha na
# chamada ou saída fora do schema também deixa passar, mas como INDISPONIVEL: não é aprovação.
MAX_TENTATIVAS = settings.llm.max_tentativas_juiz

APROVADO = "APROVADO"
REPROVADO = "REPROVADO"
INDISPONIVEL = "INDISPONIVEL"


class VereditoJuiz(BaseModel):
    """Saída estruturada do Juiz — INDISPONIVEL não é opção do LLM, só do fallback."""

    veredito:      Literal[Veredito.APROVADO, Veredito.REPROVADO]
    justificativa: str


class Criterio(StrEnum):
    """As perguntas que o JeV responde sobre a resposta; o valor é o nome da pergunta."""

    GROUNDING  = "grounding"
    RELEVANCIA = "relevancia"
    COMPLETUDE = "completude"


class Grounding(StrEnum):
    SUSTENTADA    = "sustentada"
    CONTRADIZ     = "contradiz"
    SEM_EVIDENCIA = "sem_evidencia"


DESCRICAO_GROUNDING: dict[Grounding, str] = {
    Grounding.SUSTENTADA:    "tudo o que a resposta afirma aparece nos dados",
    Grounding.CONTRADIZ:     "a resposta afirma algo diferente do que os dados mostram",
    Grounding.SEM_EVIDENCIA: "a resposta afirma algo que não aparece nos dados",
}

# O JeV não explica o veredito: o feedback pro orquestrador reescrever é uma frase por falha.
_FEEDBACK: dict[Grounding | Criterio, str] = {
    Grounding.CONTRADIZ:     "A resposta contradiz o retorno das tools; reescreva usando só esses dados.",
    Grounding.SEM_EVIDENCIA: "A resposta afirma coisas que não estão no retorno das tools; tire o que não tem respaldo.",
    Criterio.RELEVANCIA:     "A resposta não atende à pergunta original do usuário.",
    Criterio.COMPLETUDE:     "A resposta deixou parte da pergunta original sem resposta.",
}

_PREDICADOS = (Criterio.RELEVANCIA, Criterio.COMPLETUDE)

llm_avaliador = estruturado(VereditoJuiz, llm_juiz, llm_rapido, llm_luna)

_PROMPTS = load_sections("juiz.md")


def _pedido(estado: Estado) -> str:
    return _PROMPTS["template"].format(
        pergunta_original=estado.get("pergunta_original", ""),
        dados_disponiveis=estado.get("dados_especialista", ""),
        resposta_gerada=estado.get("resposta_especialista", ""),
    )


async def _avaliar_com_jev(estado: Estado) -> tuple[Veredito, str]:
    decisoes = await jev.decidir("juiz", _pedido(estado), [
        PerguntaEscolha(
            name=Criterio.GROUNDING, instructions=_PROMPTS["grounding_jev"], choices=DESCRICAO_GROUNDING
        ),
        *(PerguntaPredicado(name=criterio, instructions=_PROMPTS[f"{criterio}_jev"]) for criterio in _PREDICADOS),
    ])

def _logar(veredito: str, justificativa: str, tentativas: int, repetir: bool) -> None:
    if repetir:
        logger.warning(
            "Juiz REPROVOU (tentativa %s/%s): %s", tentativas + 1, MAX_TENTATIVAS, justificativa
        )
    elif veredito == REPROVADO:
        logger.warning(
            "Juiz REPROVOU mas as tentativas se esgotaram — seguindo mesmo assim: %s", justificativa
        )
    elif veredito == APROVADO:
        logger.info("Juiz APROVOU: %s", justificativa)

    if falhas:
        return Veredito.REPROVADO, " ".join(_FEEDBACK[falha] for falha in falhas)
    return Veredito.APROVADO, "Sustentada, relevante e completa."


async def _avaliar_com_llm(estado: Estado) -> tuple[Veredito, str]:
    avaliacao = await llm_avaliador.ainvoke([
        SystemMessage(content=load_prompt("juiz")),
        HumanMessage(content=_pedido(estado)),
    ])
    if not isinstance(avaliacao, VereditoJuiz):
        raise TypeError(f"esperava VereditoJuiz, veio {type(avaliacao).__name__}")

    return Veredito(avaliacao.veredito), avaliacao.justificativa.strip()


async def _avaliar(estado: Estado) -> tuple[Veredito, str]:
    """JeV quando o gateway está configurado; se ele falhar, o LLM; se os dois falharem, INDISPONIVEL."""

    if jev.disponivel():
        try:
            return await _avaliar_com_jev(estado)
        except Exception as e:
            logger.warning("Juiz JeV falhou, usando o LLM: %s", e)

    try:
        return await _avaliar_com_llm(estado)
    except Exception as e:
        logger.warning("Falha ao invocar Juiz (%s) — resposta segue sem avaliação: %s", type(e).__name__, e)
        veredito, justificativa = INDISPONIVEL, "Juiz indisponível: resposta entregue sem avaliação"

    reescritas = estado.get("reescritas_juiz", 0)
    reescrever = veredito == Veredito.REPROVADO and reescritas < MAX_REESCRITAS
    if reescrever:
        reescritas += 1

    _logar(veredito, justificativa, reescritas if reescrever else None)

    return JuizUpdate(
        veredito_juiz=veredito,
        justificativa_juiz=justificativa,
        feedback_juiz=justificativa if reescrever else "",
        reescritas_juiz=reescritas,
    )


__all__ = ["MAX_REESCRITAS", "Veredito", "no_juiz"]
