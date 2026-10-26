from neomodel import (
    AsyncRelationshipTo,
    AsyncStructuredNode,
    AsyncStructuredRel,
    BooleanProperty,
    FloatProperty,
    IntegerProperty,
    StringProperty,
    UniqueIdProperty,
)

from frigus_ai.infra.neo4j.models import relations
from frigus_ai.infra.neo4j.models.ingredient import Ingredient


class Requires(AsyncStructuredRel):
    quantity = FloatProperty()
    unit = StringProperty()


class Recipe(AsyncStructuredNode):
    uid = UniqueIdProperty(db_property="id")
    key = StringProperty(unique_index=True, required=True)
    source = StringProperty(required=True)
    external_id = IntegerProperty(required=True)
    name = StringProperty(required=True)
    ingredients_complete = BooleanProperty(default=False)
    fingerprint = StringProperty()
    preparation_time_minutes = IntegerProperty()
    difficulty = StringProperty()

    requires = AsyncRelationshipTo(Ingredient, relations.REQUIRES, model=Requires)
    similar_to = AsyncRelationshipTo(
        "frigus_ai.infra.neo4j.models.recipe.Recipe", relations.SIMILAR_TO
    )
