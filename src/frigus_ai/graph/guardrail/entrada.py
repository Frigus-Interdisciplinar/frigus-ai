from langchain_core.messages import AIMessage, HumanMessage

from frigus_ai.graph.guardrail.cache import (
    categoria_em_cache,
    fingerprint_do_prompt,
    guardar_categoria,
)
from frigus_ai.graph.guardrail.padroes import pede_dado_interno, tem_injecao
from frigus_ai.graph.guardrail.schemas import (
    RESPOSTAS_BLOQUEIO,
    Categoria,
    Motivo,
    ResultadoGuardrail,
)
from frigus_ai.graph.llm import llm_guardrail
from frigus_ai.graph.names import GUARDRAIL_ENTRADA
from frigus_ai.graph.nodes.contexto import perguntar, podar_historico
from frigus_ai.graph.prompts import load_sections
from frigus_ai.graph.state import Estado, GuardrailEntradaUpdate
from frigus_ai.logging import Logging
from frigus_ai.observability.metrics import GUARDRAIL_DECISIONS, medir_node
from frigus_ai.privacy import anonimizar_entrada

logger = Logging.get_logger(__name__)

_CLASSIFICADOR = load_sections("guardrail.md")["classificador"]
_FINGERPRINT = fingerprint_do_prompt(_CLASSIFICADOR)


def _bloquear(motivo: Motivo, mensagem: str) -> ResultadoGuardrail:
    return ResultadoGuardrail(bloqueado=True, motivo=motivo, mensagem=mensagem)


def _aprovado() -> ResultadoGuardrail:
    return ResultadoGuardrail(bloqueado=False, motivo="aprovado")



def _extrair_categoria(resposta: str) -> str:
    """Retorna APROVADO se o LLM não seguir o formato esperado."""

    for linha in resposta.splitlines():
        if linha.strip().upper().startswith("CATEGORIA:"):
            return linha.split(":", 1)[1].strip().upper()

    return Categoria.APROVADO


async def _classificar(mensagem_anonimizada: str) -> str:
    """Categoria do texto, do cache quando possível — senão da LLM, e então cacheada."""

    if (cacheada := categoria_em_cache(mensagem_anonimizada, _FINGERPRINT)) is not None:
        logger.debug("Classificação do guardrail veio do cache: %s", cacheada)
        return cacheada

    resposta = await perguntar(
        llm_guardrail, _CLASSIFICADOR.format(mensagem=mensagem_anonimizada)
    )
    categoria = _extrair_categoria(resposta)
    guardar_categoria(mensagem_anonimizada, _FINGERPRINT, categoria)

    return categoria


async def guardrail_entrada(mensagem_anonimizada: str) -> ResultadoGuardrail:
    """
    Executa verificações em ordem de custo crescente: determinístico primeiro,
    LLM (ou cache) só se necessário.
    """

    if tem_injecao(mensagem_anonimizada):
        return _bloquear("prompt_injection", "Não consigo processar essa solicitação.")

    if pede_dado_interno(mensagem_anonimizada):
        return _bloquear(
            "acesso_dados_internos", "Não tenho como compartilhar informações internas do sistema."
        )

    categoria = await _classificar(mensagem_anonimizada)

    # Lookup pela str crua, sem `Categoria(categoria)`: o StrEnum casa por hash de str, e
    # converter estouraria ValueError se o LLM inventasse uma categoria fora da lista —
    # o que precisa cair no `_aprovado()` abaixo (falha aberta), não derrubar o turno.
    if (bloqueio := RESPOSTAS_BLOQUEIO.get(categoria)) is not None:
        return _bloquear(bloqueio["motivo"], bloqueio["mensagem"])

    return _aprovado()


@medir_node(GUARDRAIL_ENTRADA)
async def no_guardrail_entrada(estado: Estado) -> GuardrailEntradaUpdate:
    logger.info("Verificando entrada com guardrail de entrada...")

    ultima_msg = estado["messages"][-1]
    texto_anonimizado, mapa_pii = anonimizar_entrada(ultima_msg.content)
    resultado = await guardrail_entrada(texto_anonimizado)

    GUARDRAIL_DECISIONS.labels(decision=resultado["motivo"]).inc()

    if resultado["bloqueado"]:
        logger.warning(
            "Mensagem bloqueada por guardrail: %s - %s", resultado["motivo"], texto_anonimizado
        )
        return GuardrailEntradaUpdate(
            agentes_chamados=[GUARDRAIL_ENTRADA],
            mensagem_bloqueada=resultado["mensagem"],
            messages=[
                HumanMessage(id=ultima_msg.id, content="[mensagem bloqueada]"), # salva bloqueada
                AIMessage(content=resultado["mensagem"]),
            ],
        )

    logger.info("Mensagem aprovada pelo guardrail de entrada.")

    # Poda aqui, no nó de entrada, porque é o único por onde todo turno passa — e antes do
    # roteador, pra que o histórico encurtado já valha pras chamadas de LLM deste turno.
    poda = podar_historico(estado["messages"])
    if poda:
        logger.info("Histórico podado: %s mensagens antigas removidas.", len(poda))

    return GuardrailEntradaUpdate(
        agentes_chamados=[GUARDRAIL_ENTRADA],
        mapa_pii=mapa_pii,
        messages=[*poda, HumanMessage(id=ultima_msg.id, content=texto_anonimizado)],
        mensagem_bloqueada=None, # limpa mensagem bloqueada de turnos anteriores
    )


__all__ = ["guardrail_entrada", "no_guardrail_entrada"]
