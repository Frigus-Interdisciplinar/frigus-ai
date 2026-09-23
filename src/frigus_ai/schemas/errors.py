from enum import StrEnum

from pydantic import BaseModel


class ErrorCode(StrEnum):
    CHAT_NAO_ENCONTRADO = "chat_nao_encontrado"
    CHAT_DE_OUTRO_USUARIO = "chat_de_outro_usuario"
    LIMITE_DE_MENSAGENS = "limite_de_mensagens"
    FALHA_NO_AGENTE = "falha_no_agente"
    ERRO_INTERNO = "erro_interno"
    ERRO_NO_CHAT = "erro_no_chat"
    ESTOQUE_ITEM_NAO_ENCONTRADO = "estoque_item_nao_encontrado"
    QUANTIDADE_NEGATIVA = "quantidade_negativa"
    COMPRA_ITEM_NAO_ENCONTRADO = "compra_item_nao_encontrado"
    PRODUTO_NAO_CADASTRADO = "produto_nao_cadastrado"
    ESTOQUE_NAO_DEFINIDO = "estoque_nao_definido"


class ErrorResponse(BaseModel):
    detail: str
    code: ErrorCode


__all__ = ["ErrorCode", "ErrorResponse"]
