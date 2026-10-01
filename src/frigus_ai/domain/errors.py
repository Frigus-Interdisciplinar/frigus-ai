"""
Todas as exceptions de domínio do projeto, num lugar só.

Cada classe carrega a tradução HTTP (`status_code`, `code`) e a mensagem que pode ir pro cliente
(`public_message`). `str(exc)` é a mensagem interna: vai pro log, nunca pra resposta.
"""

from enum import StrEnum

from fastapi import status


class ErrorCode(StrEnum):
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


class FrigusError(Exception):
    """Raiz de tudo que o projeto levanta de propósito."""


class DomainError(FrigusError):
    """Erro de domínio traduzível pra HTTP; subclasse só sobrescreve o que muda."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: ErrorCode = ErrorCode.ERRO_INTERNO
    public_message: str = "Não foi possível concluir a operação."


class ContextoDeSessaoError(DomainError):
    """Erro base de contexto de sessão (user_id/stock_id) do Postgres."""


class UsuarioDaSessaoNaoDefinido(ContextoDeSessaoError):
    def __init__(self) -> None:
        super().__init__("current_user_id não definido — chame dentro de session_context().")


class EstoqueAtualNaoDefinido(ContextoDeSessaoError):
    status_code = status.HTTP_409_CONFLICT
    code = ErrorCode.ESTOQUE_NAO_DEFINIDO
    public_message = "Usuário sem estoque associado."

    def __init__(self) -> None:
        super().__init__("current_stock_id não definido — usuário sem grupo/estoque associado.")


class ChatError(DomainError):
    """Erro base dos casos de uso de chat (services/chat/service.py)."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = ErrorCode.ERRO_NO_CHAT
    public_message = "Não foi possível processar o chat."


class ChatDeOutroUsuario(ChatError):
    status_code = status.HTTP_403_FORBIDDEN
    code = ErrorCode.CHAT_DE_OUTRO_USUARIO
    public_message = "Chat não pertence ao usuário atual."

    def __init__(self, chat_id: str) -> None:
        super().__init__(f"Chat {chat_id!r} pertence a outro usuário.")


class FalhaNoAgente(ChatError):
    """O grafo de agentes (LangGraph) falhou ao processar a mensagem."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = ErrorCode.FALHA_NO_AGENTE
    public_message = "O assistente falhou ao processar a mensagem."


class LimiteDeMensagensExcedido(ChatError):
    """Usuário excedeu o rate limit de mensagens do chat (services/chat/cache.py)."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = ErrorCode.LIMITE_DE_MENSAGENS
    public_message = "Limite de mensagens excedido; tente novamente em instantes."


class EstoqueError(DomainError):
    """Erro base das operações de estoque (repositories/estoque_repository.py)."""


class ItemDeEstoqueNaoEncontrado(EstoqueError):
    status_code = status.HTTP_404_NOT_FOUND
    code = ErrorCode.ESTOQUE_ITEM_NAO_ENCONTRADO
    public_message = "Nenhum item de estoque encontrado para os filtros fornecidos."

    def __init__(self) -> None:
        super().__init__("Nenhum item de estoque encontrado para os filtros fornecidos.")


class QuantidadeNegativa(EstoqueError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = ErrorCode.QUANTIDADE_NEGATIVA
    public_message = "Quantidade final não pode ser negativa."

    def __init__(self) -> None:
        super().__init__("Quantidade final não pode ser negativa.")


class ComprasError(DomainError):
    """Erro base das operações de compras (repositories/compras_repository.py)."""


class ItemDeCompraNaoEncontrado(ComprasError):
    status_code = status.HTTP_404_NOT_FOUND
    code = ErrorCode.COMPRA_ITEM_NAO_ENCONTRADO
    public_message = "Nenhum item da lista de compras encontrado para os filtros fornecidos."

    def __init__(self) -> None:
        super().__init__("Nenhum item da lista de compras encontrado para os filtros fornecidos.")


class ProdutoNaoCadastrado(ComprasError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = ErrorCode.PRODUTO_NAO_CADASTRADO
    public_message = "Produto não encontrado no catálogo; informe category e storage_place para cadastrá-lo."

    def __init__(self) -> None:
        super().__init__(
            "Produto não encontrado no catálogo; informe category e storage_place para cadastrá-lo."
        )


class PreferenciasError(DomainError):
    """Erro base das operações de preferências (repositories/preferencias_repository.py)."""


class IngredienteNaoEncontrado(PreferenciasError):
    def __init__(self, nome: str) -> None:
        super().__init__(f"Ingrediente {nome!r} não encontrado.")


class AssessorError(DomainError):
    """Erro base das chamadas A2A ao Assessor financeiro (infra/assessor/client.py)."""


class AssessorIndisponivel(AssessorError):
    """Assessor não configurado, fora do ar, ou respondeu algo que não dá pra usar."""


class SpoonacularError(DomainError):
    """Erro base das chamadas à API da Spoonacular."""


class ApiKeyNaoConfiguradaError(SpoonacularError):
    def __init__(self) -> None:
        super().__init__("SPOONACULAR_API_KEY não configurada")


class CotaExcedidaError(SpoonacularError):
    def __init__(self) -> None:
        super().__init__(
            "cota diária da API de receitas (Spoonacular) esgotada — tente novamente amanhã"
        )
