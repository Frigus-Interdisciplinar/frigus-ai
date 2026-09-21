from abc import ABC, abstractmethod

from langchain_core.tools import BaseTool


class ToolSet(ABC):
    """
    Contrato de todo domínio de tools do grafo — expõe suas tools via `as_tools()`.

    `as_tools` é método de instância, não `@tool` nos métodos: `@tool` roda no corpo
    da classe, quando `self` ainda está na assinatura, e vaza pro JSON schema que vai
    pro LLM. `StructuredTool.from_function` num bound method (`self.metodo`) resolve
    isso — a assinatura já vem sem `self`.
    """

    @abstractmethod
    def as_tools(self) -> list[BaseTool]: ...
