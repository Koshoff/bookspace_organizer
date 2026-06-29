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


def update_supplier(supplier_id, name, bulstat, mol, address, phone, email,
                    default_discount):
    """Обновява съществуващ доставчик. Връща (True, съобщение) или (False, грешка).
    Хваща нарушение на UNIQUE(name) — друг доставчик вече носи това име."""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE suppliers
               SET name = ?, bulstat = ?, mol = ?, address = ?,
                   phone = ?, email = ?, default_discount = ?
               WHERE id = ?""",
            (name, bulstat, mol, address, phone, email, default_discount,
             supplier_id)
        )
        conn.commit()
        return True, "Доставчикът е обновен успешно."
    except sqlite3.IntegrityError:
        return False, f"Вече съществува друг доставчик с име „{name}“."
    finally:
        conn.close()


def delete_supplier(supplier_id):
    """Изтрива доставчик САМО ако няма свързани книги.
    Книгите сочат към доставчика (FK), затова изтриване с останали книги
    би оставило сираци — затова го отказваме с ясно съобщение.
    Връща (True, съобщение) или (False, грешка)."""
    conn = get_connection()
    try:
        used = conn.execute(
            "SELECT COUNT(*) AS c FROM products WHERE supplier_id = ?",
            (supplier_id,)
        ).fetchone()["c"]
        if used > 0:
            return False, (f"Не може да се изтрие — има {used} книги от този "
                           f"доставчик. Първо ги прехвърлете или изтрийте.")
        conn.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
        conn.commit()
        return True, "Доставчикът е изтрит."
    finally:
        conn.close()

