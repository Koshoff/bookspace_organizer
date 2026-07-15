"""
Централизирани настройки. ВСИЧКИ тайни идват от environment / .env файл —
никога от кода и никога от git. Виж backend/.env.example.

Правило: ако някоя стойност е тайна (пароли, ключове), тя се чете тук и
НИКОГА не се връща към браузъра.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Тайни (ЗАДЪЛЖИТЕЛНИ, без стойност по подразбиране за да гръмне рано) ---
    # Генерирай с:  python -c "import secrets; print(secrets.token_urlsafe(48))"
    SECRET_KEY: str = Field(..., min_length=32)

    # --- JWT ---
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    JWT_ALGORITHM: str = "HS256"

    # --- CORS: точният origin на фронтенда, НИКОГА "*" при cookie-базиран auth ---
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # --- Cookies ---
    # В production (зад HTTPS) сложи COOKIE_SECURE=true.
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    # --- Външни услуги (тайните им стоят само тук, на сървъра) ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""     # тайна — не напуска сървъра

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.FRONTEND_ORIGIN.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
