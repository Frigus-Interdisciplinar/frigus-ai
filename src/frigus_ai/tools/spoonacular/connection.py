from functools import lru_cache

import httpx

from config.settings import settings

_BASE_URL = "https://api.spoonacular.com"


@lru_cache(maxsize=1)
def get_client() -> httpx.Client:
    """
    Cacheado em vez de criado no import: mantém a conexão reaproveitada entre
    chamadas (o ponto do client) sem abrir socket só por importar o módulo, e dá
    um objeto pra `fechar_client()` encerrar no shutdown da API.
    """

    return httpx.Client(
        base_url=_BASE_URL, params={"apiKey": settings.SPOONACULAR_API_KEY}
    )


def fechar_client() -> None:
    if get_client.cache_info().currsize:
        get_client().close()
        get_client.cache_clear()
