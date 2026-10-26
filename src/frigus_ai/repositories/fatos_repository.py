"""
Persistência crua dos fatos estruturados da conversa (alergias, preferências,
restrições, hábitos), coleção `user_fatos` no Mongo. Sem merge nem regra de
segurança (alergia só é adicionada, nunca removida pela extração automática) —
isso fica em `services/user_service.py`.
"""

from datetime import UTC, datetime

from frigus_ai.domain.models import Fatos, RecipePreferences, RecipePreferencesPatch
from frigus_ai.infra.logging import Logging
from frigus_ai.infra.mongo import mongo

logger = Logging.get_logger(__name__)

collection = None


class FatosRepository:
    def _collection(self):
        return collection or mongo.collection("user_fatos")

    def buscar_fatos(self, user_id: str) -> Fatos:
        doc = self._collection().find_one({"user_id": user_id})
        if not doc:
            return Fatos()

        return Fatos(
            alergias=doc.get("alergias", []),
            preferencias=doc.get("preferencias", []),
            restricoes=doc.get("restricoes", []),
            habitos=doc.get("habitos", []),
        )

    def salvar_fatos(self, user_id: str, fatos: Fatos) -> None:
        self._collection().update_one(
            {"user_id": user_id},
            {"$set": {**fatos.model_dump(), "updated_at": datetime.now(UTC)}},
            upsert=True,
        )

    def buscar_preferencias_receitas(self, user_id: str) -> RecipePreferences:
        doc = self._collection().find_one({"user_id": user_id}, {"recipe_preferences": 1})

        return RecipePreferences(**(doc or {}).get("recipe_preferences", {}))

    def atualizar_preferencias_receitas(self, user_id: str, patch: RecipePreferencesPatch) -> None:
        valores = patch.model_dump(exclude_none=True)
        if not valores:
            return

        self._collection().update_one(
            {"user_id": user_id},
            {
                "$set": {
                    **{f"recipe_preferences.{campo}": valor for campo, valor in valores.items()},
                    "updated_at": datetime.now(UTC),
                },
            },
            upsert=True,
        )


_fatos_repository = FatosRepository()


def buscar_fatos(user_id: str) -> Fatos:
    return _fatos_repository.buscar_fatos(user_id)


def salvar_fatos(user_id: str, fatos: Fatos) -> None:
    _fatos_repository.salvar_fatos(user_id, fatos)


def buscar_preferencias_receitas(user_id: str) -> RecipePreferences:
    return _fatos_repository.buscar_preferencias_receitas(user_id)


def atualizar_preferencias_receitas(user_id: str, patch: RecipePreferencesPatch) -> None:
    _fatos_repository.atualizar_preferencias_receitas(user_id, patch)


__all__ = [
    "atualizar_preferencias_receitas",
    "buscar_fatos",
    "buscar_preferencias_receitas",
    "salvar_fatos",
]
