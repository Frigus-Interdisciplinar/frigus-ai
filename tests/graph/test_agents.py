"""O contexto (fatos/conversas) chega ao system prompt por `context=` do ainvoke — agente real,
só o modelo é falso."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from frigus_ai.domain.models import Fatos
from frigus_ai.graph import agents
from frigus_ai.graph.state import ContextoPrompt


class _ModeloQueCapturaPrompt(BaseChatModel):
    capturado: list = Field(default_factory=list)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.capturado.append(messages)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])

    @property
    def _llm_type(self) -> str:
        return "fake"


async def _prompt_do_sistema(contexto):
    modelo = _ModeloQueCapturaPrompt()
    agente = agents._montar("faq", modelo)

    await agente.ainvoke({"messages": [HumanMessage(content="oi")]}, context=contexto)

    return modelo.capturado[0][0].content


async def test_fatos_e_conversas_entram_no_system_prompt():
    contexto = ContextoPrompt(fatos=Fatos(alergias=["amendoim"]), conversas=("comprou leite semana passada",))

    prompt = await _prompt_do_sistema(contexto)

    assert "amendoim" in prompt
    assert "comprou leite semana passada" in prompt


async def test_sem_contexto_o_prompt_sai_sem_as_secoes():
    prompt = await _prompt_do_sistema(None)

    assert "amendoim" not in prompt
