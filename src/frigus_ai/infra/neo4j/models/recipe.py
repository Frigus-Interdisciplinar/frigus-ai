from neomodel import (
    AsyncRelationshipTo,
    AsyncStructuredNode,
    AsyncStructuredRel,
    IntegerProperty,
    StringProperty,
    UniqueIdProperty,
)

from frigus_ai.infra.neo4j.models import relations
from frigus_ai.infra.neo4j.models.ingredient import Ingredient


class Requires(AsyncStructuredRel):
    quantity = IntegerProperty(required=True)
    unit = StringProperty(required=True)


class Recipe(AsyncStructuredNode):
    uid = UniqueIdProperty(db_property="id")
    name = StringProperty(required=True)
    preparation_time_minutes = IntegerProperty(required=True)
    difficulty = StringProperty(required=True)

    requires = AsyncRelationshipTo(Ingredient, relations.REQUIRES, model=Requires)
    similar_to = AsyncRelationshipTo(
        "frigus_ai.infra.neo4j.models.recipe.Recipe", relations.SIMILAR_TO
    )
