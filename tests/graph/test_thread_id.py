"""
O nó chama o agente interno (`create_agent`) sem passar `config`: o `thread_id` do grafo tem que
chegar lá por herança, senão chats concorrentes dividiriam checkpoint.
"""

import asyncio

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph


class _Modelo(BaseChatModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        ultima = messages[-1].content
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=f"eco:{ultima}"))])

    @property
    def _llm_type(self) -> str:
        return "fake"


def _grafo(checkpointer):
    agente = create_agent(model=_Modelo(), tools=[])

    async def no(estado: MessagesState):
        saida = await agente.ainvoke({"messages": estado["messages"]})  # sem config, como os nós
        return {"messages": [saida["messages"][-1]]}

    g = StateGraph(MessagesState)
    g.add_node("no", no)
    g.add_edge(START, "no")
    g.add_edge("no", END)
    return g.compile(checkpointer=checkpointer)


async def test_threads_concorrentes_nao_misturam_checkpoint():
    memoria = MemorySaver()
    grafo = _grafo(memoria)

    async def turno(thread_id, texto):
        await grafo.ainvoke(
            {"messages": [HumanMessage(content=texto)]}, config={"configurable": {"thread_id": thread_id}}
        )

    await asyncio.gather(turno("chat-a", "alfa"), turno("chat-b", "beta"))

    for thread_id, proprio, alheio in (("chat-a", "alfa", "beta"), ("chat-b", "beta", "alfa")):
        estado = await grafo.aget_state({"configurable": {"thread_id": thread_id}})
        conteudo = " ".join(m.content for m in estado.values["messages"])
        assert proprio in conteudo
        assert alheio not in conteudo
