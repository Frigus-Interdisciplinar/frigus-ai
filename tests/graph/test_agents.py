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


async def _prompt_do_sistema(contexto, agente="receitas"):
    modelo = _ModeloQueCapturaPrompt()
    agente = agents._montar(agente, modelo)

    await agente.ainvoke({"messages": [HumanMessage(content="oi")]}, context=contexto)

    return modelo.capturado[0][0].content


async def test_fatos_e_conversas_entram_no_system_prompt():
    contexto = ContextoPrompt(fatos=Fatos(alergias=["amendoim"]), conversas=("comprou leite semana passada",))

    prompt = await _prompt_do_sistema(contexto)

    assert "amendoim" in prompt
    assert "comprou leite semana passada" in prompt


async def test_perfil_so_vai_pros_agentes_que_personalizam():
    contexto = ContextoPrompt(fatos=Fatos(alergias=["amendoim"]), conversas=("comprou leite semana passada",))

    assert "amendoim" in await _prompt_do_sistema(contexto, "compras")
    for agente in ("estoque", "faq", "financeiro", "router", "orquestrador"):
        prompt = await _prompt_do_sistema(contexto, agente)
        assert "amendoim" not in prompt, agente
        assert "comprou leite semana passada" in prompt, agente


async def test_campo_vazio_do_perfil_sai_como_nao_informado():
    """"nenhuma" fazia o LLM tratar falta de cadastro como "não tem alergia"."""

    prompt = await _prompt_do_sistema(ContextoPrompt(fatos=Fatos(preferencias=["massa"])))

    assert "- Alergias: não informado" in prompt
    assert "- Preferências: massa" in prompt


async def test_sem_contexto_o_prompt_sai_sem_as_secoes():
    prompt = await _prompt_do_sistema(None)

    assert "amendoim" not in prompt
