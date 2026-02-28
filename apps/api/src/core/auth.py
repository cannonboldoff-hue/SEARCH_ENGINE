import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt

from src.core.config import get_settings


_MAX_BCRYPT_BYTES = 72  # bcrypt limit


def verify_password(plain: str, hashed: str) -> bool:
    try:
        pwd_bytes = plain.encode("utf-8")[:_MAX_BCRYPT_BYTES]
        return bcrypt.checkpw(pwd_bytes, hashed.encode("utf-8"))
    except (ValueError, TypeError, Exception):
        return False


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:_MAX_BCRYPT_BYTES]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")


def create_access_token(subject: str) -> str:
    s = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expire_minutes)
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, s.jwt_secret, algorithm=s.jwt_algorithm)


def create_photo_token(subject: str, expire_minutes: int | None = None) -> str:
    """Token for profile photo URL so <img> can load without Bearer. Does not expire by default."""
    s = get_settings()
    if expire_minutes is not None:
        expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
        to_encode = {"sub": subject, "exp": expire}
    else:
        # No expiry: profile photos are stored in DB and URLs should work indefinitely
        to_encode = {"sub": subject}
    return jwt.encode(to_encode, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> Optional[str]:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
        sub = payload.get("sub")
        return str(sub) if sub is not None else None
    except JWTError:
        return None
