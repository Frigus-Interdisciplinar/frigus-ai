"""Todas as exceptions de domínio do projeto, num lugar só."""


class FrigusError(Exception):
    """Erro base do projeto — toda exception de domínio herda daqui."""


class ServiceError(FrigusError):
    """Erro base dos services."""


class ContextoDeSessaoError(FrigusError):
    """Erro base de contexto de sessão (user_id/stock_id) do Postgres."""


class UsuarioDaSessaoNaoDefinido(ContextoDeSessaoError):
    def __init__(self) -> None:
        super().__init__("current_user_id não definido — chame dentro de session_context().")


class EstoqueAtualNaoDefinido(ContextoDeSessaoError):
    def __init__(self) -> None:
        super().__init__("current_stock_id não definido — usuário sem grupo/estoque associado.")


class ChatError(FrigusError):
    """Erro base dos casos de uso de chat (services/chat/service.py)."""


class ChatNaoEncontrado(ChatError):
    def __init__(self, chat_id: str) -> None:
        super().__init__(f"Chat {chat_id!r} não encontrado.")


class ChatDeOutroUsuario(ChatError):
    def __init__(self, chat_id: str) -> None:
        super().__init__(f"Chat {chat_id!r} pertence a outro usuário.")


class FalhaNoAgente(ChatError):
    """O grafo de agentes (LangGraph) falhou ao processar a mensagem."""


class LimiteDeMensagensExcedido(ChatError):
    """Usuário excedeu o rate limit de mensagens do chat (services/chat/cache.py)."""


class EstoqueError(FrigusError):
    """Erro base das operações de estoque (repositories/estoque_repository.py)."""


class ItemDeEstoqueNaoEncontrado(EstoqueError):
    def __init__(self) -> None:
        super().__init__("Nenhum item de estoque encontrado para os filtros fornecidos.")


class QuantidadeNegativa(EstoqueError):
    def __init__(self) -> None:
        super().__init__("Quantidade final não pode ser negativa.")


class ComprasError(FrigusError):
    """Erro base das operações de compras (repositories/compras_repository.py)."""


class ItemDeCompraNaoEncontrado(ComprasError):
    def __init__(self) -> None:
        super().__init__("Nenhum item da lista de compras encontrado para os filtros fornecidos.")


class ProdutoNaoCadastrado(ComprasError):
    def __init__(self) -> None:
        super().__init__(
            "Produto não encontrado no catálogo; informe category e storage_place para cadastrá-lo."
        )


class PreferenciasError(FrigusError):
    """Erro base das operações de preferências (repositories/preferencias_repository.py)."""


class IngredienteNaoEncontrado(PreferenciasError):
    def __init__(self, nome: str) -> None:
        super().__init__(f"Ingrediente {nome!r} não encontrado.")


class AssessorError(FrigusError):
    """Erro base das chamadas A2A ao Assessor financeiro (infra/assessor/client.py)."""


class AssessorIndisponivel(AssessorError):
    """Assessor não configurado, fora do ar, ou respondeu algo que não dá pra usar."""


class SpoonacularError(FrigusError):
    """Erro base das chamadas à API da Spoonacular."""


class ApiKeyNaoConfiguradaError(SpoonacularError):
    def __init__(self) -> None:
        super().__init__("SPOONACULAR_API_KEY não configurada")


class CotaExcedidaError(SpoonacularError):
    def __init__(self) -> None:
        super().__init__(
            "cota diária da API de receitas (Spoonacular) esgotada — tente novamente amanhã"
        )
