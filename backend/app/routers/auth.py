"""
Автентикация: login / refresh / logout / me.

Токените се доставят като httpOnly, Secure, SameSite cookies — така браузърът
ги праща автоматично, но JavaScript не може да ги чете (защита срещу XSS кражба).
Login-ът е rate-limited срещу brute force.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from app import operators
from app.config import get_settings
from app.deps import ACCESS_COOKIE, REFRESH_COOKIE, get_current_operator
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class OperatorOut(BaseModel):
    username: str
    role: str
    full_name: str = ""


def _set_auth_cookies(response: Response, username: str, role: str) -> None:
    s = get_settings()
    common = dict(
        httponly=True,
        secure=s.COOKIE_SECURE,
        samesite=s.COOKIE_SAMESITE,
        path="/",
    )
    response.set_cookie(
        ACCESS_COOKIE,
        create_access_token(username, role),
        max_age=s.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **common,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        create_refresh_token(username, role),
        max_age=s.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        **common,
    )


@router.post("/login", response_model=OperatorOut)
@limiter.limit("5/minute")
def login(request: Request, response: Response, body: LoginBody):
    op = operators.authenticate(body.username, body.password)
    if op is None:
        # Едно и също съобщение за грешно име И грешна парола (без user enumeration).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Грешно потребителско име или парола.",
        )
    _set_auth_cookies(response, op["username"], op["role"])
    return OperatorOut(username=op["username"], role=op["role"],
                       full_name=op["full_name"])


@router.post("/refresh", response_model=OperatorOut)
def refresh(request: Request, response: Response):
    token = request.cookies.get(REFRESH_COOKIE)
    payload = decode_token(token, expected_type="refresh") if token else None
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сесията изтече, влезте отново.",
        )
    op = operators.get_by_username(payload["sub"])
    if op is None or not op["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Акаунтът е недостъпен.")
    _set_auth_cookies(response, op["username"], op["role"])
    return OperatorOut(username=op["username"], role=op["role"],
                       full_name=op["full_name"])


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")
    return {"detail": "Излязохте успешно."}


@router.get("/me", response_model=OperatorOut)
def me(operator: dict = Depends(get_current_operator)):
    op = operators.get_by_username(operator["username"])
    full = op["full_name"] if op else ""
    return OperatorOut(username=operator["username"], role=operator["role"],
                       full_name=full)
