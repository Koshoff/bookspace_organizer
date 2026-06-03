from db.connection import get_connection
# само АКО функцията хваща sqlite3.IntegrityError:
import sqlite3

# ---------- КРЕДИТНИ ИЗВЕСТИЯ / СТОРНО (Модул 6) ----------

def cancel_sale(sale_id, original_receipt, operator="система"):
    """
    Отказва продажба в една транзакция:
    1) сменя статуса на 'Отказана',
    2) връща всяка книга на склад (движение 'Сторно' с ПЛЮС),
    3) записва кредитно известие с номера на оригиналната касова бележка.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        # Защита: продажби с ваучер НЕ подлежат на сторно.
        # Политика на бизнеса (ваучерите не се връщат) И техническо ограничение
        # (CHECK ограничението прави складовото движение за ваучер невъзможно).
        voucher_row = cur.execute(
            """SELECT COUNT(*) AS c FROM sale_items
               WHERE sale_id = ? AND voucher_id IS NOT NULL""",
            (sale_id,)
        ).fetchone()
        if voucher_row["c"] > 0:
            conn.rollback()
            return False, ("Тази продажба съдържа ваучер. "
                           "Ваучерите не подлежат на връщане/сторниране.")

        # Първо взимаме редовете на продажбата — трябват ни, за да върнем книгите.
        items = cur.execute(
            "SELECT product_id, quantity, sale_price FROM sale_items WHERE sale_id = ?",
            (sale_id,)
        ).fetchall()

        if not items:
            conn.rollback()
            return False, "Продажбата няма редове за връщане."

        # Сборът, който връщаме на клиента (за журнала на сторната).
        returned_amount = sum(i["quantity"] * i["sale_price"] for i in items)

        # 1) Статусът → 'Отказана'
        cur.execute(
            "UPDATE sales SET status = 'Отказана', payment_date = NULL WHERE id = ?",
            (sale_id,)
        )

        # 2) Връщане на всяка книга на склад: движение 'Сторно' с ПЛЮС.
        for item in items:
            cur.execute(
                """INSERT INTO stock_movements
                   (product_id, movement_type, quantity_change, document_ref, operator)
                   VALUES (?, 'Сторно', ?, ?, ?)""",
                (item["product_id"], item["quantity"],   # ПЛЮС — връщаме на склад
                 f"Кредитно известие (бележка №{original_receipt})", operator)
            )

        # 3) Запис на кредитното известие
        cur.execute(
            """INSERT INTO credit_notes (sale_id, original_receipt, returned_amount)
               VALUES (?, ?, ?)""",
            (sale_id, original_receipt, returned_amount)
        )

        conn.commit()
        return True, f"Сторнирана продажба. Върнати на склад: {len(items)} вид(а) книги."

    except Exception as e:
        conn.rollback()
        return False, f"Грешка при сторното: {e}"
    finally:
        conn.close()


def get_credit_notes(year_month=None):
    """
    Връща кредитните известия, опционално филтрирани по месец (формат 'YYYY-MM').
    strftime изважда годината-месец от датата за филтъра.
    """
    conn = get_connection()
    query = """
        SELECT
            cn.id,
            cn.created_at,
            cn.original_receipt,
            cn.returned_amount,
            s.order_number,
            s.id AS sale_id
        FROM credit_notes cn
        JOIN sales s ON s.id = cn.sale_id
    """
    params = []
    if year_month is not None:
        query += " WHERE strftime('%Y-%m', cn.created_at) = ?"
        params.append(year_month)
    query += " ORDER BY cn.created_at DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows