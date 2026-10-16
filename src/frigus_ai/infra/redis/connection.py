from __future__ import annotations

from frigus_ai.infra.base import Connector
from frigus_ai.settings import settings
from redis import Redis

# `Redis[str]` porque `decode_responses=True` devolve str; o `__future__` existe porque `Redis`
# não é subscritável em runtime.


class RedisConn(Connector[Redis]):
    def __init__(self) -> None:
        self._client: Redis[str] | None = None

    def connect(self) -> Redis[str]:
        if self._client is None:
            # Sem timeout, o redis-py espera o TCP do SO e repete com backoff (~4s por chamada com
            # o Redis fora). Ele só serve cache e rate limit: melhor falhar rápido.
            self._client = Redis.from_url(
                settings.database.redis_url,
                decode_responses=True,
                socket_connect_timeout=3.0,
                socket_timeout=3.0,
                retry_on_timeout=False,
            )
        return self._client

    @property
    def client(self) -> Redis[str]:
        return self.connect()


redis = RedisConn()


def get_client() -> Redis[str]:
    return redis.client


__all__ = ["RedisConn", "get_client", "redis"]
