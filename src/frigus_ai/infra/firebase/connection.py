import firebase_admin
from firebase_admin import App, credentials
from google.auth.credentials import AnonymousCredentials

from frigus_ai.infra.base import Connector
from frigus_ai.settings import settings


class _SemCredencial(credentials.Base):
    """Validar o ID token usa só as chaves públicas do Google, não uma service account. O cliente do
    Admin SDK exige alguma credencial ao iniciar, então esta entrega uma vazia."""

    def get_credential(self) -> AnonymousCredentials:
        return AnonymousCredentials()


class FirebaseConn(Connector[App]):
    def __init__(self) -> None:
        self._app: App | None = None

    def connect(self) -> App:
        if self._app is None:
            path = settings.api_keys.firebase_credentials_path
            projeto = settings.api_keys.firebase_project_id
            if path:
                cred = credentials.Certificate(path)
            elif projeto:
                cred = _SemCredencial()
            else:
                cred = credentials.ApplicationDefault()
            self._app = firebase_admin.initialize_app(cred, {"projectId": projeto} if projeto else None)
        return self._app

    @property
    def app(self) -> App:
        return self.connect()

    def fechar(self) -> None:
        if self._app is not None:
            firebase_admin.delete_app(self._app)
            self._app = None


firebase = FirebaseConn()


def get_firebase_app() -> App:
    return firebase.app


__all__ = ["FirebaseConn", "firebase", "get_firebase_app"]
