from pydantic import BaseModel, SecretStr


class ObservabilitySettings(BaseModel):
    langsmith_tracing: bool
    langsmith_api_key: SecretStr
    langsmith_project: str
    prometheus_url: str = ""
