from pydantic import BaseModel, SecretStr


class DatabaseSettings(BaseModel):
    postgres_uri: str
    mongodb_uri: str
    neo4j_uri: str
    redis_url: str
    qdrant_url: str
    qdrant_api_key: SecretStr = SecretStr("")
    qdrant_collection_name: str
    qdrant_chats_collection: str = "chats"
