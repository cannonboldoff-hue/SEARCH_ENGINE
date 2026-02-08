from .auth import router as auth_router
from .profile import router as profile_router
from .contact import router as contact_router
from .builder import router as builder_router
from .search import router as search_router

ROUTERS = (auth_router, profile_router, contact_router, builder_router, search_router)

__all__ = [
    "ROUTERS",
    "auth_router",
    "profile_router",
    "contact_router",
    "builder_router",
    "search_router",
]
