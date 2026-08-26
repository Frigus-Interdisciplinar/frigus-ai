from redis import Redis

from config.settings import settings

_client: Redis | None = None


def get_client() -> Redis:
    global _client

    if _client is None:
        _client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    return _client
