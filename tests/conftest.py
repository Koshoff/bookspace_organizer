"""
Обща настройка за тестовете.

- Стъбва 'streamlit', за да може да се импортира mailer.py без инсталиран Streamlit.
- fresh_db fixture: чиста временна SQLite база от schema.sql, към която сочи
  целият db слой (чрез monkeypatch на db.connection.DB_FILE).
"""
import os
import sys
import types

import pytest

# --- Стъб за streamlit (mailer.send_supplier_email вика st.success) ---
if "streamlit" not in sys.modules:
    _fake_st = types.ModuleType("streamlit")
    _fake_st.success = lambda *a, **k: None
    _fake_st.error = lambda *a, **k: None
    sys.modules["streamlit"] = _fake_st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = os.path.join(ROOT, "schema.sql")


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Връща db модула, вързан към празна временна база с актуалната схема."""
    import sqlite3
    import db.connection as conn_mod

    dbfile = str(tmp_path / "test.db")
    monkeypatch.setattr(conn_mod, "DB_FILE", dbfile)

    conn = sqlite3.connect(dbfile)
    with open(SCHEMA, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

    import db
    return db


@pytest.fixture
def run_sql(fresh_db):
    """Помощник за директен SQL върху тестовата база (напр. фиксиране на дати)."""
    def _run(query, params=()):
        conn = fresh_db.get_connection()
        cur = conn.execute(query, params)
        rows = cur.fetchall()
        conn.commit()
        conn.close()
        return rows
    return _run


# --- Малки помощници за наливане на данни ---

@pytest.fixture
def seed(fresh_db):
    db = fresh_db

    def _supplier(name="Сиела", discount=40.0, email="office@ciela.bg"):
        db.add_supplier(name, "123", "МОЛ", "адрес", "тел", email, discount)
        return [s for s in db.get_all_suppliers() if s["name"] == name][0]["id"]

    def _product(isbn, title, supplier_id, cover=20.0, author="Автор",
                 product_type="Книга", fiscal_group="Б", vat=9, critical=3):
        db.add_product(isbn, title, author, supplier_id, cover, vat, 2024,
                       "мека", "жанр", "опис", product_type=product_type,
                       fiscal_group=fiscal_group, critical_minimum=critical)
        return [p for p in db.get_all_products_full() if p["isbn"] == isbn][0]["id"]

    def _deliver(supplier_id, product_id, qty, price, settlement="Купена",
                 doc="D1", date="2026-06-01", percent=40.0,
                 payment="По банка"):
        return db.create_delivery(
            supplier_id, "Фактура", doc, date,
            [{"product_id": product_id, "quantity": qty,
              "settlement_type": settlement, "supplier_percent": percent,
              "delivery_price": price}], payment)

    ns = types.SimpleNamespace(supplier=_supplier, product=_product,
                               deliver=_deliver, db=db)
    return ns
