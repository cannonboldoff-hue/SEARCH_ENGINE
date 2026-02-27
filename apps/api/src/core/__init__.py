"""Core configuration, auth, and shared infrastructure."""

from src.core.config import Settings, get_settings
from src.core.constants import EMBEDDING_DIM, SEARCH_NEVER_EXPIRES
from src.core.auth import (
    verify_password,
    hash_password,
    create_access_token,
    create_photo_token,
    decode_access_token,
)
from src.core.limiter import limiter

__all__ = [
    "Settings",
    "get_settings",
    "EMBEDDING_DIM",
    "SEARCH_NEVER_EXPIRES",
    "verify_password",
    "hash_password",
    "create_access_token",
    "create_photo_token",
    "decode_access_token",
    "limiter",
]
