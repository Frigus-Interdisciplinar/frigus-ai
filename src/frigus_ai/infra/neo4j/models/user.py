from neomodel import (
    AsyncRelationshipTo,
    AsyncStructuredNode,
    StringProperty,
    UniqueIdProperty,
)

from frigus_ai.infra.neo4j.models import relations
from frigus_ai.infra.neo4j.models.ingredient import Ingredient


class User(AsyncStructuredNode):
    uid = UniqueIdProperty(db_property="id")
    name = StringProperty(required=True)

    prefers = AsyncRelationshipTo(Ingredient, relations.PREFERS)
    dislikes = AsyncRelationshipTo(Ingredient, relations.DISLIKES)
    allergic_to = AsyncRelationshipTo(Ingredient, relations.ALLERGIC_TO)
