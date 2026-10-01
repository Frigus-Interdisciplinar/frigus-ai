import re

from langchain_core.messages import AIMessage

from frigus_ai.domain.privacy import (
    PII_USUARIO,
    MapaPII,
    desanonimizar_saida,
    redigir_pii,
)
from frigus_ai.graph.guardrail.schemas import ResultadoGuardrail, RevisaoCompliance
from frigus_ai.graph.llm import llm_rapido
from frigus_ai.graph.names import GUARDRAIL_SAIDA
from frigus_ai.graph.prompts import load_sections
from frigus_ai.graph.state import Estado, GuardrailSaidaUpdate
from frigus_ai.infra.logging import Logging
from frigus_ai.observability import medir_node

logger = Logging.get_logger(__name__)

_COMPLIANCE = load_sections("guardrail.md")["compliance"]

llm_revisor = llm_rapido.with_structured_output(RevisaoCompliance) if llm_rapido else None

_SINAIS_DE_RISCO = re.compile(
    r"segur[oa]\s+(para|pra)\s+(o\s+)?(consumo|comer)|sem\s+(nenhum\s+)?risco"
    r"|n[aã]o\s+(tem|h[aá])\s+risco|garant"
    r"|sa[uú]de|nutri|dieta|diagn[oó]st|m[eé]dic|tratamento|doen[çc]a|rem[eé]dio"
    r"|sintoma|alerg|diabet|colesterol|gr[aá]vid|emagrec"
    r"|100\s*%|com\s+(toda\s+)?certeza|pode\s+confiar|sem\s+d[uú]vida"
    r"|n[aã]o\s+(vai\s+)?estragar|nunca\s+(vai\s+)?estraga"
    r"|composi[çc][aã]o\s+corporal|[ií]ndice\s+glic[eê]mico",
    re.IGNORECASE,
)


def precisa_revisao(resposta: str) -> bool:
    return _SINAIS_DE_RISCO.search(resposta) is not None


def _saida_ok(conteudo: str) -> ResultadoGuardrail:
    return ResultadoGuardrail(
        bloqueado=False,
        motivo="saida_revisada",
        conteudo=conteudo
    )



async def guardrail_saida(
    resposta: str,
    mapa_pii: MapaPII,
    restaurar_pii: bool = False
) -> ResultadoGuardrail:
    """
    Nunca bloqueia — sempre retorna o texto revisado. Só chama o LLM quando
    `precisa_revisao`; falha ou saída fora do schema mantém a resposta original.
    """

    resposta = redigir_pii(resposta, PII_USUARIO)
    resposta = desanonimizar_saida(resposta, mapa_pii, restaurar=restaurar_pii)

    if not precisa_revisao(resposta):
        return _saida_ok(resposta)

    try:
        revisao = await llm_revisor.ainvoke(_COMPLIANCE.format(resposta=resposta))
        if not isinstance(revisao, RevisaoCompliance):
            raise TypeError(f"esperava RevisaoCompliance, veio {type(revisao).__name__}")
    except Exception as e:
        logger.warning("Revisão de compliance falhou, mantendo a resposta original: %s", e)
        return _saida_ok(resposta)

    return _saida_ok(revisao.revisada.strip() or resposta)


@medir_node(GUARDRAIL_SAIDA)
async def no_guardrail_saida(estado: Estado) -> GuardrailSaidaUpdate:

    logger.info("Revisando resposta do especialista com guardrail de saída...")
    resultado = await guardrail_saida(
        estado["resposta_especialista"],
        estado.get("mapa_pii", {})
    )

    return GuardrailSaidaUpdate(
        agentes_chamados=[GUARDRAIL_SAIDA],
        messages=[AIMessage(content=resultado["conteudo"])],
    )


__all__ = ["no_guardrail_saida"]
