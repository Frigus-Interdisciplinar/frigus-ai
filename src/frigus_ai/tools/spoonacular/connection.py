import httpx

from config.settings import settings

_BASE_URL = "https://api.spoonacular.com"


def _conectar() -> httpx.Client:

    return httpx.Client(
        base_url=_BASE_URL, params={"apiKey": settings.SPOONACULAR_API_KEY}
    )


cliente = _conectar()
