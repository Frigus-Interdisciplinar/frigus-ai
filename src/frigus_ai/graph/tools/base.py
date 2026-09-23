import inspect
from abc import ABC, abstractmethod

from langchain_core.tools import BaseTool

from frigus_ai.graph.tools.response import Response
from frigus_ai.logging import Logging

_METODOS_IGNORADOS = frozenset({"as_tools"})


class ToolSet(ABC):
    """
    Contrato de todo domínio de tools do grafo — expõe suas tools via `as_tools()`.

    `as_tools` é método de instância, não `@tool` nos métodos: `@tool` roda no corpo
    da classe, quando `self` ainda está na assinatura, e vaza pro JSON schema que vai
    pro LLM. `StructuredTool.from_function` num bound method (`self.metodo`) resolve
    isso — a assinatura já vem sem `self`.

    Todo método público de toda subclasse já sai com `Response.catch` (exception vira
    `Response.error`) + logado (`Logging.log_classe`, igual `Connector` em
    `infra/base.py`) — não precisa de `@Response.catch`/`@Logging.log_tool` método a
    método. `as_tools` fica de fora: só monta a lista pro LangChain, não é uma
    chamada de tool.
    """

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)

        for nome, atributo in list(vars(cls).items()):
            if nome.startswith("_") or nome in _METODOS_IGNORADOS or not inspect.isfunction(atributo):
                continue
            setattr(cls, nome, Response.catch(atributo))

        Logging.log_classe(ignore=_METODOS_IGNORADOS)(cls)

    @abstractmethod
    def as_tools(self) -> list[BaseTool]: ...
