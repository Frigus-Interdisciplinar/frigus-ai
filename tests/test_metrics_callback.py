"""
Custo e fallback no callback Prometheus: o node vem do nosso grafo (não do node interno do
`create_agent`), custo = tokens × tabela, e especialista respondendo fora do Gemini é fallback.
"""

from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from frigus_ai.graph.names import ESTOQUE
from frigus_ai.settings.llm import Model
from frigus_ai.telemetry.metrics import LLM_COST, LLM_FALLBACKS
from frigus_ai.telemetry.metrics_callback import PrometheusCallbackHandler, custo_usd


def _rodar(modelo: str, metadata: dict) -> None:
    handler = PrometheusCallbackHandler()
    run_id = uuid4()
    handler.on_chat_model_start(
        {}, [[]], run_id=run_id,
        metadata={"ls_provider": "groq", "ls_model_name": modelo, **metadata},
    )
    mensagem = AIMessage(
        content="ok",
        usage_metadata={"input_tokens": 1_000_000, "output_tokens": 1_000_000, "total_tokens": 2_000_000},
    )
    handler.on_llm_end(LLMResult(generations=[[ChatGeneration(message=mensagem)]]), run_id=run_id)


def test_custo_usa_a_tabela_e_modelo_desconhecido_custa_zero():
    assert custo_usd(Model.GPT_OSS_120B, 1_000_000, 1_000_000) == 0.15 + 0.60
    assert custo_usd("modelo-novo", 1_000_000, 1_000_000) == 0.0


def test_fallback_no_especialista_conta_pelo_node_do_grafo():
    antes = LLM_FALLBACKS.labels(node=ESTOQUE, model=Model.GPT_OSS_120B)._value.get()
    custo_antes = LLM_COST.labels(provider="groq", model=Model.GPT_OSS_120B)._value.get()

    # dentro do create_agent, langgraph_node é "model"; o nosso node vem no checkpoint_ns
    _rodar(Model.GPT_OSS_120B, {"langgraph_node": "model", "langgraph_checkpoint_ns": f"{ESTOQUE}:abc|model:def"})

    assert LLM_FALLBACKS.labels(node=ESTOQUE, model=Model.GPT_OSS_120B)._value.get() == antes + 1
    assert LLM_COST.labels(provider="groq", model=Model.GPT_OSS_120B)._value.get() == custo_antes + 0.75


def test_modelo_principal_no_especialista_nao_e_fallback():
    antes = LLM_FALLBACKS.labels(node=ESTOQUE, model=Model.GEMINI_FLASH)._value.get()

    _rodar(Model.GEMINI_FLASH, {"langgraph_checkpoint_ns": f"{ESTOQUE}:abc"})

    assert LLM_FALLBACKS.labels(node=ESTOQUE, model=Model.GEMINI_FLASH)._value.get() == antes
