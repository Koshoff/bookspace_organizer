"""
Криптографски примитиви: хеширане на пароли (bcrypt) и JWT токени.

Паролите НИКОГА не се пазят в чист текст — само bcrypt хеш. JWT се подписва
със SECRET_KEY от config-а.
"""
import base64
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import get_settings


def _prehash(plain: str) -> bytes:
    """SHA-256 → base64, за да няма значение 72-байтовата граница на bcrypt
    (дълга парола/UTF-8 не се отрязва тихо)."""
    digest = hashlib.sha256(plain.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_prehash(plain), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(plain), hashed.encode("ascii"))
    except ValueError:
        return False


def _create_token(sub: str, role: str, expires: timedelta, kind: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,          # потребителско име
        "role": role,        # admin / cashier
        "type": kind,        # access / refresh
        "iat": now,
        "exp": now + expires,
    }
    return jwt.encode(payload, s.SECRET_KEY, algorithm=s.JWT_ALGORITHM)


def create_access_token(username: str, role: str) -> str:
    s = get_settings()
    return _create_token(
        username, role, timedelta(minutes=s.ACCESS_TOKEN_EXPIRE_MINUTES), "access"
    )


def create_refresh_token(username: str, role: str) -> str:
    s = get_settings()
    return _create_token(
        username, role, timedelta(days=s.REFRESH_TOKEN_EXPIRE_DAYS), "refresh"
    )


def decode_token(token: str, expected_type: str) -> dict | None:
    """Връща payload или None при невалиден/изтекъл/грешен тип токен."""
    s = get_settings()
    try:
        payload = jwt.decode(token, s.SECRET_KEY, algorithms=[s.JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload
