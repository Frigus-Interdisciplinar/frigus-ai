from __future__ import annotations

from frigus_ai.infra.base import Connector
from frigus_ai.settings import settings
from redis import Redis

# decode_responses=True faz o client devolver str, não bytes — `Redis[str]` nas
# anotações deixa isso explícito pro type checker (senão .get() aparece como
# bytes | str | None). `from __future__ import annotations` porque a classe `Redis`
# instalada não é subscritável em runtime — só nas anotações, que ficam como string.


class RedisConn(Connector[Redis]):
    def __init__(self) -> None:
        self._client: Redis[str] | None = None

    def connect(self) -> Redis[str]:
        if self._client is None:
            # Timeouts explícitos: o default do redis-py é esperar o TCP do SO e ainda
            # repetir com backoff — medido em ~4s POR chamada com o Redis fora do ar.
            # Redis aqui só serve cache e rate limit, nada que justifique segurar o
            # request: melhor falhar rápido e seguir sem cache.
            self._client = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
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
