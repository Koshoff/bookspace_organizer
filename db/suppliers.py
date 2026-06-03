from db.connection import get_connection
# само АКО функцията хваща sqlite3.IntegrityError:
import sqlite3


# ---------- ДОСТАВЧИЦИ (Модул 1) ----------

def add_supplier(name, bulstat, mol, address, phone, email, default_discount):
    """Добавя нов доставчик. Връща (True, съобщение) или (False, грешка)."""
    conn = get_connection()
    try:
        # Параметризирана заявка с ? — НИКОГА не слепвай стойности в SQL низа
        # с f-string! Това е защита срещу SQL injection и счупване при кавички.
        conn.execute(
            """INSERT INTO suppliers
               (name, bulstat, mol, address, phone, email, default_discount)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, bulstat, mol, address, phone, email, default_discount)
        )
        conn.commit()
        return True, "Доставчикът е добавен успешно."
    except sqlite3.IntegrityError:
        # Хваща нарушение на UNIQUE — значи вече има доставчик с това име.
        return False, f"Вече съществува доставчик с име „{name}“."
    finally:
        conn.close()  # винаги затваряме връзката, дори при грешка


def get_all_suppliers():
    """Връща всички доставчици, подредени по име."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM suppliers ORDER BY name"
    ).fetchall()
    conn.close()
    return rows

