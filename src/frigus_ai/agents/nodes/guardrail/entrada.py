import re
import uuid

from langchain_core.messages import HumanMessage

from config.logging import get_logger
from frigus_ai.agents.nodes.names import Node
from frigus_ai.agents.prompts.guardrail import GuardrailPrompts
from frigus_ai.graph.llm import llm_guardrail
from frigus_ai.graph.state import Estado

logger = get_logger(__name__)

from frigus_ai.agents.nodes.guardrail.schemas import (
    _KEYWORDS_DADOS_INTERNOS,
    _PADROES_INJECAO,
    _RESPOSTAS_BLOQUEIO,
    PII,
    Categoria,
    ResultadoGuardrail,
)


def _bloquear(motivo: str, mensagem: str) -> ResultadoGuardrail:
    return ResultadoGuardrail(
        bloqueado=True,
        motivo=motivo,
        mensagem=mensagem
    )


def _aprovado() -> ResultadoGuardrail:
    return ResultadoGuardrail(
        bloqueado=False,
        motivo="aprovado"
    )


def anonimizar_entrada(texto: str) -> tuple[str, dict]:
    mapa = {}

    for tipo, padrao in PII:
        for valor in re.findall(padrao, texto):
            token = f"[PII_{tipo}_{uuid.uuid4().hex[:6]}]"
            mapa[token] = valor
            texto = texto.replace(valor, token, 1)

    return texto, mapa


def _extrair_categoria(resposta: str) -> str:
    """
    Retorna APROVADO se o LLM não seguir o formato esperado.
    """

    for linha in resposta.splitlines():
        if linha.strip() \
                .upper() \
                .startswith("CATEGORIA:"):

            return linha.split(":", 1)[1].strip().upper()

    return Categoria.APROVADO


def _detectar_injecao(texto: str) -> bool:
    return any(
        re.search(p, texto, re.IGNORECASE)
        for p in _PADROES_INJECAO
    )

def _detectar_acesso_interno(texto: str) -> bool:
    return any(
        w in texto.lower()
        for w in _KEYWORDS_DADOS_INTERNOS
    )


def guardrail_entrada(mensagem_anonimizada: str) -> ResultadoGuardrail:
    """
    Executa verificações em ordem de custo crescente:
    determinístico primeiro, LLM só se necessário.
    """

    if _detectar_injecao(mensagem_anonimizada):
        return _bloquear("prompt_injection", "Não consigo processar essa solicitação.")

    if _detectar_acesso_interno(mensagem_anonimizada):
        return _bloquear("acesso_dados_internos", "Não tenho como compartilhar informações internas do sistema.")

    mensagem = llm_guardrail.invoke(
                GuardrailPrompts.CLASSIFICADOR.format(mensagem=mensagem_anonimizada)
            ).content

    categoria = _extrair_categoria(mensagem)

    if categoria in _RESPOSTAS_BLOQUEIO:
        motivo, mensagem = _RESPOSTAS_BLOQUEIO[categoria]
        return _bloquear(motivo, mensagem)

    return _aprovado()


def no_guardrail_entrada(estado: Estado) -> dict:
    logger.info("Verificando entrada com guardrail de entrada...")

    ultima_msg = estado["messages"][-1]
    texto_anonimizado, mapa_pii = anonimizar_entrada(ultima_msg.content)
    resultado = guardrail_entrada(texto_anonimizado)

    if resultado["bloqueado"]:
        logger.warning(f"Mensagem bloqueada por guardrail: {resultado['motivo']} - {ultima_msg.content}")
        return {
            "agentes_chamados":   [Node.GUARDRAIL_ENTRADA],
            "mensagem_bloqueada": resultado["mensagem"],
            "messages": [
                HumanMessage(id=ultima_msg.id, content="[mensagem bloqueada]"), # salva bloqueada
                {"role": "assistant", "content": resultado["mensagem"]},
            ],
        }

    logger.info("Mensagem aprovada pelo guardrail de entrada.")
    return {
        "agentes_chamados":   [Node.GUARDRAIL_ENTRADA],
        "mapa_pii":           mapa_pii,
        "messages":           [HumanMessage(id=ultima_msg.id, content=texto_anonimizado)],
        "mensagem_bloqueada": None, # limpa mensagem bloqueada de turnos anteriores
    }


__all__ = ["no_guardrail_entrada"]
