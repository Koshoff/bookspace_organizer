"""
Входна точка на FastAPI backend-а за Bookspace.

Стартиране (от папка backend/):
    uvicorn app.main:app --reload

Изисква backend/.env със SECRET_KEY (виж .env.example).
Увива съществуващия db/ пакет — не дублира бизнес логика.
"""
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Позволяваме "import db" от коренната папка на проекта (два слоя нагоре).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO_ROOT)

import db.connection  # noqa: E402
# Базата винаги е в корена на проекта, независимо от работната папка на uvicorn.
# Може да се пренасочи с environment променливата BOOKSPACE_DB (напр. споделен диск).
db.connection.DB_FILE = os.environ.get(
    "BOOKSPACE_DB", os.path.join(_REPO_ROOT, "bookspace.db")
)

from app import operators                       # noqa: E402
from app.config import get_settings             # noqa: E402
from app.routers import auth, catalog, dashboard  # noqa: E402

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    operators.ensure_table()   # гарантира, че таблицата operators съществува
    yield


app = FastAPI(title="Bookspace API", version="0.1.0", lifespan=lifespan)

# --- Rate limiting (споделяме лимитъра от auth рутера) ---
app.state.limiter = auth.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS: само точния origin на фронтенда + cookies ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,        # нужно за cookie-базиран auth
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(dashboard.router)
