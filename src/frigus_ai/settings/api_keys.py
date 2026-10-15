from pydantic import BaseModel, SecretStr


class ApiKeysSettings(BaseModel):
    """Segredos de autenticação e keys de serviços externos que não são LLM (as de LLM ficam em `llm`)."""

    signup_secret: SecretStr = SecretStr("")
    metrics_token: SecretStr = SecretStr("")
    spoonacular_api_key: SecretStr = SecretStr("")
    assessor_api_key: SecretStr = SecretStr("")
    # Caminho do JSON da service account do Firebase. Vazio = Application Default Credentials.
    firebase_credentials_path: str = ""
    # Segredo do HMAC que identifica as API keys no Redis. Vazio = SHA-256 puro. Trocar (ou
    # ligar depois de já ter emitido keys) invalida todas as keys existentes.
    hash_secret: SecretStr = SecretStr("")
