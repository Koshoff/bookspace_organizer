"""
Тестове за FastAPI backend-а (auth + защита на endpoint-и).

Ползва fresh_db фикстурата (временна SQLite), за да не пипа реалната база.
SECRET_KEY се задава преди импорта на app, защото config-ът се кешира.
"""
import os
import sys

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long-xx")
os.environ.setdefault("COOKIE_SECURE", "false")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

httpx = pytest.importorskip("httpx")
fastapi = pytest.importorskip("fastapi")
pytest.importorskip("jose")
pytest.importorskip("bcrypt")
pytest.importorskip("slowapi")

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client(fresh_db):
    """TestClient, чийто backend сочи към временната тестова база."""
    import db.connection
    from app.main import app
    from app import operators

    # Backend-ът чете DB_FILE от db.connection — fresh_db вече го е насочил.
    operators.ensure_table()
    operators.create_operator("admin", "secret123", "Тест Админ", "admin")
    operators.create_operator("kasa", "cashier123", "Каса 1", "cashier")
    with TestClient(app) as c:
        yield c


def _login(client, username, password):
    return client.post("/api/auth/login",
                       json={"username": username, "password": password})


def test_health_is_public(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_login_success_sets_httponly_cookies(client):
    r = _login(client, "admin", "secret123")
    assert r.status_code == 200
    assert r.json()["role"] == "admin"
    cookies = "\n".join(r.headers.get_list("set-cookie")).lower()
    assert "bookspace_access" in cookies and "httponly" in cookies
    assert "samesite=lax" in cookies


def test_wrong_password_and_unknown_user_are_indistinguishable(client):
    r1 = _login(client, "admin", "WRONG")
    r2 = _login(client, "does-not-exist", "whatever")
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"]  # без user enumeration


def test_protected_endpoint_requires_session(client):
    fresh = TestClient(client.app)
    assert fresh.get("/api/catalog/products").status_code == 401
    assert fresh.get("/api/auth/me").status_code == 401


def test_full_session_lifecycle(client):
    assert _login(client, "admin", "secret123").status_code == 200
    assert client.get("/api/auth/me").json()["username"] == "admin"
    assert client.get("/api/catalog/products").json() == []  # празен каталог
    assert client.post("/api/auth/refresh").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401       # cookies изтрити


def test_password_is_hashed_not_plaintext(fresh_db):
    from app import operators
    operators.ensure_table()
    operators.create_operator("x", "myplainpw", "", "cashier")
    row = operators.get_by_username("x")
    assert row["password_hash"] != "myplainpw"
    assert row["password_hash"].startswith("$2")   # bcrypt формат
