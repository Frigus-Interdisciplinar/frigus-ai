from pydantic import BaseModel, SecretStr


class ApiKeysSettings(BaseModel):
    """Segredos de autenticação e keys de serviços externos que não são LLM (as de LLM ficam em `llm`)."""

    signup_secret: SecretStr = SecretStr("")
    metrics_token: SecretStr = SecretStr("")
    spoonacular_api_key: SecretStr = SecretStr("")
    assessor_api_key: SecretStr = SecretStr("")
    # Validar o ID token do login só precisa do ID do projeto (`project_info.project_id` do
    # google-services.json). A service account só é necessária pra outras APIs do Admin SDK.
    firebase_project_id: str = ""
    # Caminho do JSON da service account. Vazio = Application Default Credentials.
    firebase_credentials_path: str = ""
    # Segredo do HMAC que identifica as API keys no Redis. Vazio = SHA-256 puro. Trocar (ou
    # ligar depois de já ter emitido keys) invalida todas as keys existentes.
    hash_secret: SecretStr = SecretStr("")
