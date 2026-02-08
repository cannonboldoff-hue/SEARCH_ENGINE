from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.auth import decode_access_token


def get_rate_limit_key(request):
    """Per-user rate limit when authenticated; else per IP. Multi-instance needs Redis later."""
    auth = request.headers.get("Authorization") or ""
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        if token:
            uid = decode_access_token(token)
            if uid:
                return f"user:{uid}"
    return get_remote_address(request)


limiter = Limiter(key_func=get_rate_limit_key)
