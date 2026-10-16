from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Overwrite

from frigus_ai.domain.privacy import anonimizar_entrada
from frigus_ai.graph.guardrail.cache import (
    categoria_em_cache,
    fingerprint_do_prompt,
    guardar_categoria,
)
from frigus_ai.graph.guardrail.padroes import pede_dado_interno, tem_injecao
from frigus_ai.graph.guardrail.schemas import (
    DESCRICAO_CATEGORIA,
    RESPOSTAS_BLOQUEIO,
    Categoria,
    Classificacao,
    Motivo,
    ResultadoGuardrail,
    listar_categorias,
)
from frigus_ai.graph.llm import estruturado, llm_guardrail, llm_luna, llm_rapido
from frigus_ai.graph.names import GUARDRAIL_ENTRADA
from frigus_ai.graph.nodes.contexto import podar_historico
from frigus_ai.graph.prompts import load_sections
from frigus_ai.graph.state import Estado, GuardrailEntradaUpdate
from frigus_ai.infra.llm import jev
from frigus_ai.infra.logging import Logging
from frigus_ai.settings.llm import Model
from frigus_ai.telemetry.metrics import GUARDRAIL_DECISIONS, medir_node

logger = Logging.get_logger(__name__)

_PROMPTS = load_sections("guardrail.md")


def _bloquear(motivo: Motivo, mensagem: str) -> ResultadoGuardrail:
    return ResultadoGuardrail(bloqueado=True, motivo=motivo, mensagem=mensagem)


def _aprovado() -> ResultadoGuardrail:
    return ResultadoGuardrail(bloqueado=False, motivo="aprovado")


llm_classificador = estruturado(Classificacao, llm_guardrail, llm_rapido, llm_luna)


def _fingerprint() -> str:
    """JeV e LLM podem discordar sobre a mesma mensagem: cada um tem o seu cache."""

    classificador = Model.JEV if jev.disponivel() else "llm"
    return fingerprint_do_prompt(classificador + _PROMPTS["classificador"] + listar_categorias())


async def _perguntar(mensagem_anonimizada: str) -> Categoria:
    """JeV quando o Vercel AI Gateway está configurado; senão a cadeia de LLMs."""

    if jev.disponivel():
        return await jev.escolher(
            "guardrail_entrada", mensagem_anonimizada, _PROMPTS["instrucao_jev"], DESCRICAO_CATEGORIA
        )

    prompt = _PROMPTS["classificador"].format(categorias=listar_categorias(), mensagem=mensagem_anonimizada)
    resultado = await llm_classificador.ainvoke(prompt)
    if not isinstance(resultado, Classificacao):
        raise TypeError(f"esperava Classificacao, veio {type(resultado).__name__}")

    return resultado.categoria


async def _classificar(mensagem_anonimizada: str) -> str:
    """
    Categoria do texto, do cache quando possível — senão do classificador, e então cacheada.

    Falha aberta: erro de chamada ou saída fora do schema aprova (os bloqueios por regex já
    rodaram) e NÃO vai pro cache, pra próxima mensagem igual tentar classificar de novo.
    """

    fingerprint = _fingerprint()
    if (cacheada := categoria_em_cache(mensagem_anonimizada, fingerprint)) is not None:
        logger.debug("Classificação do guardrail veio do cache: %s", cacheada)
        return cacheada

    if llm_classificador is None and not jev.disponivel():
        logger.warning("Classificador do guardrail sem API key — aprovando sem classificar.")
        return Categoria.APROVADO

    try:
        categoria = await _perguntar(mensagem_anonimizada)
    except Exception as e:
        logger.warning("Classificador do guardrail falhou, aprovando (falha aberta): %s", e)
        return Categoria.APROVADO

    guardar_categoria(mensagem_anonimizada, fingerprint, categoria)

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
            motivo="acesso_dados_internos", 
            mensagem="Não tenho como compartilhar informações internas do sistema."
        )

    categoria = await _classificar(mensagem_anonimizada)

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
            mensagem_bloqueada=resultado["mensagem"],
            messages=[
                HumanMessage(id=ultima_msg.id, content="[mensagem bloqueada]"),
                AIMessage(content=resultado["mensagem"]),
            ],
        )

    logger.info("Mensagem aprovada pelo guardrail de entrada.")

    poda = podar_historico(estado["messages"])
    if poda:
        logger.info("Histórico podado: %s mensagens antigas removidas.", len(poda))

    return GuardrailEntradaUpdate(
        mapa_pii=mapa_pii,
        messages=[*poda, HumanMessage(id=ultima_msg.id, content=texto_anonimizado)],
        mensagem_bloqueada=None, 
        dados_especialistas=Overwrite([]),
        reescritas_juiz=0,
        feedback_juiz="",
        pergunta_original=texto_anonimizado,
    )


__all__ = ["guardrail_entrada", "no_guardrail_entrada"]
