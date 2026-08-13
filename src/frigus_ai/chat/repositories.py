import frigus_ai.tools.mongo.chats.core as chats
import frigus_ai.tools.mongo.users.core as perfis
from frigus_ai.chat.models import ChatMessage, Role
from frigus_ai.tools.mongo.chats.schemas import Mensagem


def _para_mensagem(msg: ChatMessage) -> Mensagem:
    return Mensagem(role=msg.role, content=msg.content)


def _de_mensagem(msg: Mensagem) -> ChatMessage:
    return ChatMessage(role=Role(msg.role), content=msg.content)


def buscar_perfil(user_id: int) -> str:
    return perfis.buscar_perfil(user_id)


def garantir_perfil(user_id: int) -> None:
    perfis.garantir_perfil(user_id)


def buscar_historico(session_id: str, limit: int = 5) -> list[ChatMessage]:
    doc = chats.buscar(session_id, limit=limit)
    if not doc:
        return []
    return [_de_mensagem(m) for m in Mensagem.de_dict(doc["messages"])]


def salvar_mensagens(user_id: int, session_id: str, mensagens: list[ChatMessage]) -> None:
    mensagens_mongo = [_para_mensagem(m) for m in mensagens]
    if not chats.buscar(session_id):
        chats.criar(user_id, session_id, mensagens_mongo)
    else:
        chats.atualizar_mensagens(session_id, mensagens_mongo)


def encerrar_sessao(session_id: str, user_id: int) -> None:
    chats.encerrar_sessao(session_id, user_id)
