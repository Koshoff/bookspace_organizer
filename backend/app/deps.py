"""
Зависимости за защита на endpoint-и: извличане на текущия оператор от
httpOnly access-cookie и проверка на роля.

Токенът се чете от cookie (не от JavaScript-достъпно място), затова XSS не
може да го открадне.
"""
from fastapi import Cookie, Depends, HTTPException, status

from app.security import decode_token

ACCESS_COOKIE = "bookspace_access"
REFRESH_COOKIE = "bookspace_refresh"


def get_current_operator(
    bookspace_access: str | None = Cookie(default=None),
) -> dict:
    if not bookspace_access:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Не сте влезли."
        )
    payload = decode_token(bookspace_access, expected_type="access")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Изтекла или невалидна сесия.",
        )
    return {"username": payload["sub"], "role": payload.get("role", "cashier")}


def require_admin(operator: dict = Depends(get_current_operator)) -> dict:
    if operator["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нужни са администраторски права.",
        )
    return operator
