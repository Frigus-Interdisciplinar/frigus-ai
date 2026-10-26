from neomodel import AsyncStructuredNode, StringProperty, UniqueIdProperty


class Ingredient(AsyncStructuredNode):
    uid = UniqueIdProperty(db_property="id")
    key = StringProperty(unique_index=True, required=True)
    name = StringProperty(required=True)
    category = StringProperty()
