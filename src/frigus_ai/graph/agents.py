from langchain.agents import create_agent
from langchain.agents.middleware import dynamic_prompt

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


def _montar(nome: str, model, tools: list | None = None):
    """
    O system_prompt vai por `dynamic_prompt` (middleware), não por `system_prompt=`:
    o prompt carrega a data/hora atual, e como string fixa ela congelava no import —
    um processo de API vivo respondia "hoje" com a data em que subiu. O parse do .md
    continua cacheado no loader; só o contexto temporal é remontado a cada chamada.
    """

    @dynamic_prompt
    def _prompt(request) -> str:
        return load_prompt(nome)

    return create_agent(model=model, tools=tools or [], middleware=[_prompt])


router_app       = _montar("router",       llm_rapido)
estoque_app      = _montar("estoque",      llm_especialista, ESTOQUE_TOOLS)
compras_app      = _montar("compras",      llm_especialista, COMPRAS_TOOLS)
receitas_app     = _montar("receitas",     llm_especialista, RECEITAS_TOOLS)
faq_app          = _montar("faq",          llm_rapido,       FAQ_TOOLS)
financeiro_app   = _montar("financeiro",   llm_especialista, FINANCEIRO_TOOLS)
orquestrador_app = _montar("orquestrador", llm_rapido)


__all__ = [
    "compras_app",
    "estoque_app",
    "faq_app",
    "financeiro_app",
    "orquestrador_app",
    "receitas_app",
    "router_app",
]
