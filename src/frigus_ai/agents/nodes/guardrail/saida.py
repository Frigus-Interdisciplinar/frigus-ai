import re

from config.logging import get_logger
from frigus_ai.agents.nodes.guardrail.schemas import (
    PII,
    PII_USUARIO,
    ResultadoGuardrail,
)
from frigus_ai.agents.nodes.names import Node
from frigus_ai.agents.prompts.guardrail import GuardrailPrompts
from frigus_ai.graph.llm import llm_rapido
from frigus_ai.graph.state import Estado

logger = get_logger(__name__)


def _saida_ok(conteudo: str) -> ResultadoGuardrail:
    return ResultadoGuardrail(
        bloqueado=False,
        motivo="saida_revisada",
        conteudo=conteudo
    )


def desanonimizar_saida(
    texto: str,
    mapa: dict,
    restaurar: bool = False
) -> str:
    """
    Por padrão omite o valor original,
    não repete dado pessoal na saída.
    """

    for token, valor in mapa.items():
        if token not in texto:
            continue

        substituto = valor if restaurar else f"[{token.split('_')[1]} OMITIDO]"
        texto = texto.replace(token, substituto)

    return texto


def _redigir_pii(texto: str, pii_list: list = PII) -> str:
    for tipo, padrao in pii_list:
        texto = re.sub(padrao, f"[{tipo} OMITIDO]", texto)
    return texto


def guardrail_saida(
    resposta: str,
    mapa_pii: dict,
    restaurar_pii: bool = False
) -> ResultadoGuardrail:
    """
    Nunca bloqueia — sempre retorna o texto revisado. Fallback para a resposta original
    se o LLM não seguir o formato esperado.
    """

    resposta = _redigir_pii(resposta, pii_list=PII_USUARIO)
    resposta = desanonimizar_saida(resposta, mapa_pii, restaurar=restaurar_pii)

    saida = llm_rapido.invoke(
        GuardrailPrompts.COMPLIANCE.format(resposta=resposta)
    ).content.strip()

    if "RESPOSTA:" not in saida:
        return _saida_ok(resposta)

    revisada = saida.split("RESPOSTA:", 1)[1].strip()
    return _saida_ok(revisada or resposta)


def no_guardrail_saida(estado: Estado) -> dict:

    logger.info("Revisando resposta do especialista com guardrail de saída...")
    resultado = guardrail_saida(
        estado["resposta_especialista"],
        estado.get("mapa_pii", {})
    )

    return {
        "agentes_chamados": [Node.GUARDRAIL_SAIDA],
        "messages":         [{"role": "assistant", "content": resultado["conteudo"]}],
    }


__all__ = ["no_guardrail_saida"]
