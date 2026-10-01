from pydantic import BaseModel


class ApiSettings(BaseModel):
    key_auth_enabled: bool
    cors_origins: list[str] = ["*"]
    reload: bool = False
    a2a_base_url: str
    assessor_a2a_url: str = ""
