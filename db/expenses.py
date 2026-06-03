from db.connection import get_connection


def add_expense(date, category, description, amount, document_number=None):
    """
    Записва нов оперативен разход.
    date — дата на издаване на разхода (YYYY-MM-DD).
    Връща (True, съобщение) или (False, грешка).
    """
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO operating_expenses
               (date, category, description, amount, document_number)
               VALUES (?, ?, ?, ?, ?)""",
            (date, category, description, amount, document_number)
        )
        conn.commit()
        return True, "Разходът е записан успешно."
    except Exception as e:
        return False, f"Грешка при запис: {e}"
    finally:
        conn.close()


def get_expenses_by_period(date_from=None, date_to=None, category=None):
    """
    Връща всички разходи в зададения период, филтрирани по date (дата на издаване),
    не по created_at. Подреждани от най-новия към най-стария.
    """
    conn = get_connection()
    query = "SELECT * FROM operating_expenses"
    conditions, params = [], []

    if date_from is not None:
        conditions.append("date >= ?")
        params.append(date_from)
    if date_to is not None:
        conditions.append("date <= ?")
        params.append(date_to)
    if category is not None:
        conditions.append("category = ?")
        params.append(category)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY date DESC, id DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_expense(expense_id):
    """
    Изтрива разход по id. Връща True/False за успех.
    Безусловно изтриване — разходите нямат FK от други таблици, безопасно е.
    """
    conn = get_connection()
    try:
        conn.execute("DELETE FROM operating_expenses WHERE id = ?", (expense_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def get_expenses_total_by_period(date_from, date_to):
    """
    Връща общата сума на разходите за периода. Използва се от таблото
    за пресмятане на „Общо разходи" заедно с доставната стойност на продадените книги.
    """
    conn = get_connection()
    row = conn.execute(
        """SELECT COALESCE(SUM(amount), 0) AS total
           FROM operating_expenses
           WHERE date >= ? AND date <= ?""",
        (date_from, date_to)
    ).fetchone()
    conn.close()
    return row["total"]