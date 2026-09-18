from langchain_core.messages import AIMessage

from frigus_ai.evals.metrics import medir_node
from frigus_ai.graph.guardrail.schemas import ResultadoGuardrail
from frigus_ai.graph.llm import llm_rapido
from frigus_ai.graph.names import GUARDRAIL_SAIDA
from frigus_ai.graph.nodes.contexto import perguntar
from frigus_ai.graph.prompts import load_sections
from frigus_ai.graph.state import Estado, GuardrailSaidaUpdate
from frigus_ai.logging import Logging
from frigus_ai.privacy import (
    PII_USUARIO,
    MapaPII,
    desanonimizar_saida,
    redigir_pii,
)

logger = Logging.get_logger(__name__)

_COMPLIANCE = load_sections("guardrail.md")["compliance"]


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
    Nunca bloqueia — sempre retorna o texto revisado. Fallback para a resposta original
    se o LLM não seguir o formato esperado.
    """

    resposta = redigir_pii(resposta, PII_USUARIO)
    resposta = desanonimizar_saida(resposta, mapa_pii, restaurar=restaurar_pii)

    saida = (await perguntar(llm_rapido, _COMPLIANCE.format(resposta=resposta))).strip()

    if "RESPOSTA:" not in saida:
        return _saida_ok(resposta)

    revisada = saida.split("RESPOSTA:", 1)[1].strip()
    return _saida_ok(revisada or resposta)


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
