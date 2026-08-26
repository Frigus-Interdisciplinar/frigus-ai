from langchain.agents import create_agent

from frigus_ai.agents.prompts.loader import load_prompt
from frigus_ai.graph.llm import (
    llm_especialista,
    llm_rapido,
)
from frigus_ai.tools import (
    COMPRAS_TOOLS,
    ESTOQUE_TOOLS,
    FAQ_TOOLS,
    FINANCEIRO_TOOLS,
    RECEITAS_TOOLS,
)

router_app = create_agent(
    model=llm_rapido,
    system_prompt=load_prompt("router"),
)

estoque_app = create_agent(
    model=llm_especialista,
    tools=ESTOQUE_TOOLS,
    system_prompt=load_prompt("estoque"),
)

compras_app = create_agent(
    model=llm_especialista,
    tools=COMPRAS_TOOLS,
    system_prompt=load_prompt("compras"),
)

receitas_app = create_agent(
    model=llm_especialista,
    tools=RECEITAS_TOOLS,
    system_prompt=load_prompt("receitas"),
)

faq_app = create_agent(
    model=llm_rapido,
    tools=FAQ_TOOLS,
    system_prompt=load_prompt("faq"),
)

financeiro_app = create_agent(
    model=llm_especialista,
    tools=FINANCEIRO_TOOLS,
    system_prompt=load_prompt("financeiro"),
)

orquestrador_app = create_agent(
    model=llm_rapido,
    system_prompt=load_prompt("orquestrador"),
)


__all__ = [
    "compras_app",
    "estoque_app",
    "faq_app",
    "financeiro_app",
    "orquestrador_app",
    "receitas_app",
    "router_app",
]
