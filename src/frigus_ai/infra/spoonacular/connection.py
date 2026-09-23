import httpx

from frigus_ai.infra.base import Connector
from frigus_ai.settings import settings


class SpoonacularConnector(Connector[httpx.AsyncClient]):
    """
    Cliente HTTP da API da Spoonacular. Implementa o contrato `Connector`
    (`connect()`), o que dá logging automático (CHAMANDO/OK/ERRO por método)
    via `Connector.__init_subclass__` — sem precisar decorar nada aqui.
    """

    _BASE_URL = "https://api.spoonacular.com"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def connect(self) -> httpx.AsyncClient:
        """
        Cacheado na instância em vez de criado no import: mantém a conexão
        reaproveitada entre chamadas sem abrir socket só por importar o módulo.
        """

        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._BASE_URL,
                params={"apiKey": settings.SPOONACULAR_API_KEY.get_secret_value()},
            )

        return self._client

    async def fechar_async(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


spoonacular = SpoonacularConnector()

__all__ = ["SpoonacularConnector", "spoonacular"]
