from pydantic import BaseModel, EmailStr, Field

from frigus_ai.domain.types import APIKey, UserID


class KeyCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    email: EmailStr = Field(max_length=320)


class KeyCreateResponse(BaseModel):
    user_id: UserID
    api_key: APIKey
