from fastapi import APIRouter

from .chats import router as chats_router
from .profile import router as profile_router
from .recipes import router as recipes_router
from .shopping import router as shopping_router
from .stock import router as stock_router

# Só rotas de domínio levam o prefixo de versão.
v1_router = APIRouter(prefix="/v1")
for _router in (chats_router, stock_router, shopping_router, recipes_router, profile_router):
    v1_router.include_router(_router)

__all__ = ["v1_router"]
