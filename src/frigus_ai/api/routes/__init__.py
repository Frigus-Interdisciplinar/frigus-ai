from .a2a import router as a2a_router
from .chats import router as chats_router
from .health import router as health_router
from .keys import router as keys_router
from .profile import router as profile_router
from .recipes import router as recipes_router
from .shopping import router as shopping_router
from .stock import router as stock_router

__all__ = [
    "a2a_router",
    "chats_router",
    "health_router",
    "keys_router",
    "profile_router",
    "recipes_router",
    "shopping_router",
    "stock_router",
]
