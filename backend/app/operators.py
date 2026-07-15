"""
Оператори (потребители на системата) — auth слой над съществуващата SQLite база.

Ползва същата връзка като db/ пакета (db.connection.get_connection), затова
таблицата живее в bookspace.db заедно с останалите. Съхраняваме само bcrypt
хеш на паролата, никога чист текст.
"""
from db.connection import get_connection
from app.security import hash_password, verify_password

ROLES = ("admin", "cashier")

# Постоянен валиден bcrypt хеш за фалшива проверка при несъществуващ потребител.
_DUMMY_HASH = hash_password("bookspace-dummy-constant")


def ensure_table() -> None:
    """Създава таблицата operators при липса. Идемпотентно."""
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS operators (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,
            full_name     TEXT NOT NULL DEFAULT '',
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'cashier',
            is_active     INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    conn.close()


def get_by_username(username: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM operators WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_operators() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, username, full_name, role, is_active, created_at "
        "FROM operators ORDER BY username"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_operator(username: str, password: str, full_name: str = "",
                    role: str = "cashier") -> tuple[bool, str]:
    if role not in ROLES:
        return False, f"Невалидна роля: {role}"
    if len(password) < 6:
        return False, "Паролата трябва да е поне 6 знака."
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO operators (username, full_name, password_hash, role) "
            "VALUES (?, ?, ?, ?)",
            (username.strip(), full_name.strip(), hash_password(password), role),
        )
        conn.commit()
        return True, "Операторът е създаден."
    except Exception as exc:  # UNIQUE(username) или друго
        if "UNIQUE" in str(exc):
            return False, "Вече съществува оператор с това потребителско име."
        return False, f"Грешка: {exc}"
    finally:
        conn.close()


def authenticate(username: str, password: str) -> dict | None:
    """Връща оператора при валидни данни и активен акаунт, иначе None.

    Проверяваме паролата дори при несъществуващ потребител (постоянно време),
    за да не издаваме кои имена съществуват (user enumeration)."""
    op = get_by_username(username)
    if op is None:
        # Фалшива проверка с постоянно време — да не издаваме кои имена съществуват.
        verify_password(password, _DUMMY_HASH)
        return None
    if not op["is_active"]:
        return None
    if not verify_password(password, op["password_hash"]):
        return None
    return op


def count_operators() -> int:
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) AS n FROM operators").fetchone()["n"]
    conn.close()
    return n
