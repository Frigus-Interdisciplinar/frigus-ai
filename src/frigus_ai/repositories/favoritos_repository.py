"""
Persistência crua dos favoritos de receita, coleção `recipe_favorites` no Mongo. Guarda um retrato
do card (nome/imagem) pra listar sem consultar a Spoonacular de novo — a cota é paga por chamada.
"""

from datetime import UTC, datetime
from typing import TypedDict

from frigus_ai.infra.mongo import mongo

collection = None


class Favorito(TypedDict):
    source: str
    recipe_id: int
    name: str
    image_url: str | None


class FavoritosRepository:
    def __init__(self) -> None:
        self._indice_collection = None

    def _collection(self):
        colecao = collection or mongo.collection("recipe_favorites")
        if colecao is not self._indice_collection:
            colecao.create_index([("user_id", 1), ("source", 1), ("recipe_id", 1)], unique=True)
            self._indice_collection = colecao

        return colecao

    def favoritar(self, user_id: str, favorito: Favorito) -> None:
        chave = {"user_id": user_id, "source": favorito["source"], "recipe_id": favorito["recipe_id"]}

        self._collection().update_one(
            chave,
            {
                "$set": {"name": favorito["name"], "image_url": favorito["image_url"]},
                "$setOnInsert": {"created_at": datetime.now(UTC)},
            },
            upsert=True,
        )

    def desfavoritar(self, user_id: str, source: str, recipe_id: int) -> None:
        self._collection().delete_one({"user_id": user_id, "source": source, "recipe_id": recipe_id})

    def listar(self, user_id: str, limit: int) -> list[Favorito]:
        docs = self._collection().find({"user_id": user_id}).sort("created_at", -1).limit(limit)

        return [
            {
                "source": d["source"],
                "recipe_id": d["recipe_id"],
                "name": d["name"],
                "image_url": d.get("image_url"),
            }
            for d in docs
        ]


_favoritos = FavoritosRepository()


def favoritar(user_id: str, favorito: Favorito) -> None:
    _favoritos.favoritar(user_id, favorito)


def desfavoritar(user_id: str, source: str, recipe_id: int) -> None:
    _favoritos.desfavoritar(user_id, source, recipe_id)


def listar_favoritos(user_id: str, limit: int) -> list[Favorito]:
    return _favoritos.listar(user_id, limit)


__all__ = ["Favorito", "desfavoritar", "favoritar", "listar_favoritos"]
