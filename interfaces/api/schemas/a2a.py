"""
Subconjunto do protocolo A2A (Agent Card + `message/send`), escrito à mão em Pydantic.

Sem a dependência `a2a-sdk` (que o assessor-ai usa): o card declara
`streaming=false`/`pushNotifications=false`, então a superfície real é uma operação
só — `message/send`. Task store, streaming e cancelamento, que é o que o SDK traz de
fato, seriam código morto aqui. Se streaming ou tasks entrarem no card, aí o SDK passa
a valer e estes modelos saem.

O protocolo é camelCase — daí os `alias`; `populate_by_name` mantém o construtor
em snake_case do lado Python.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _CardModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class AgentCapabilities(_CardModel):
    streaming: bool = False
    push_notifications: bool = Field(default=False, alias="pushNotifications")


class AgentSkill(_CardModel):
    id: str
    name: str
    description: str
    tags: list[str]
    examples: list[str] = []


class AgentProvider(_CardModel):
    organization: str
    url: str


class AgentCard(_CardModel):
    protocol_version: str = Field(alias="protocolVersion")
    name: str
    description: str
    url: str
    version: str
    provider: AgentProvider
    capabilities: AgentCapabilities
    default_input_modes: list[str] = Field(alias="defaultInputModes")
    default_output_modes: list[str] = Field(alias="defaultOutputModes")
    skills: list[AgentSkill]


# --------------------- message/send (JSON-RPC 2.0) ---------------------

class TextPart(_CardModel):
    kind: Literal["text"] = "text"
    text: str


class Message(_CardModel):
    kind: Literal["message"] = "message"
    message_id: str = Field(alias="messageId")
    role: Literal["user", "agent"]
    parts: list[TextPart]
    # contextId agrupa a conversa entre chamadas — é o nosso session_id.
    context_id: str | None = Field(default=None, alias="contextId")

    def texto(self) -> str:
        return "\n".join(p.text for p in self.parts)


class MessageSendParams(_CardModel):
    message: Message


class JsonRpcRequest(_CardModel):
    jsonrpc: Literal["2.0"]
    id: str | int
    method: str
    params: dict = {}


class JsonRpcError(_CardModel):
    code: int
    message: str


class JsonRpcResponse(_CardModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None
    result: Message | None = None
    error: JsonRpcError | None = None
