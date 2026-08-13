from langchain.agents import create_agent

from frigus_ai.agents.prompts.compras import ComprasPrompts
from frigus_ai.agents.prompts.estoque import EstoquePrompts
from frigus_ai.agents.prompts.faq import FaqPrompts
from frigus_ai.agents.prompts.financeiro import FinanceiroPrompts
from frigus_ai.agents.prompts.orquestrador import OrquestradorPrompts
from frigus_ai.agents.prompts.receitas import ReceitasPrompts
from frigus_ai.agents.prompts.router import RouterPrompts
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
    system_prompt=RouterPrompts.system_prompt(),
)

estoque_app = create_agent(
    model=llm_especialista,
    tools=ESTOQUE_TOOLS,
    system_prompt=EstoquePrompts.system_prompt(),
)

compras_app = create_agent(
    model=llm_especialista,
    tools=COMPRAS_TOOLS,
    system_prompt=ComprasPrompts.system_prompt(),
)

receitas_app = create_agent(
    model=llm_especialista,
    tools=RECEITAS_TOOLS,
    system_prompt=ReceitasPrompts.system_prompt(),
)

faq_app = create_agent(
    model=llm_rapido,
    tools=FAQ_TOOLS,
    system_prompt=FaqPrompts.system_prompt(),
)

financeiro_app = create_agent(
    model=llm_especialista,
    tools=FINANCEIRO_TOOLS,
    system_prompt=FinanceiroPrompts.system_prompt(),
)

orquestrador_app = create_agent(
    model=llm_rapido,
    system_prompt=OrquestradorPrompts.system_prompt(),
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
