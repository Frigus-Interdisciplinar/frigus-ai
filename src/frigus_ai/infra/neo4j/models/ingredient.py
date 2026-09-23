from neomodel import AsyncStructuredNode, StringProperty, UniqueIdProperty


class Ingredient(AsyncStructuredNode):
    uid = UniqueIdProperty(db_property="id")
    name = StringProperty(required=True)
    category = StringProperty(required=True)
