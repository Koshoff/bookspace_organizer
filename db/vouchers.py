from db.connection import get_connection
# само АКО функцията хваща sqlite3.IntegrityError:
import sqlite3


def issue_voucher(nominal, payment_method="В брой (Каса)"):
    """
    Издава нов ваучер със срок една година: създава продажба с 0% ДДС
    (ваучерът сам по себе си е необлагаем при издаване), генерира уникален
    код и записва ваучера със статус 'Активен'.
    payment_method: как клиентът плаща ВАУЧЕРА (брой/карта/банка).
    """
    from datetime import date, timedelta

    conn = get_connection()
    try:
        cur = conn.cursor()

        year = date.today().year
        row = cur.execute(
            "SELECT COUNT(*) AS c FROM vouchers WHERE code LIKE ?",
            (f"GIFT-{year}-%",)
        ).fetchone()
        code = f"GIFT-{year}-{row['c'] + 1:05d}"
        valid_until = (date.today() + timedelta(days=365)).isoformat()

        cur.execute(
            """INSERT INTO sales (order_number, status, payment_method, payment_date)
               VALUES (?, 'Платена', ?, datetime('now','localtime'))""",
            (f"VOUCHER-{code}", payment_method)
        )
        sale_id = cur.lastrowid

        cur.execute(
            """INSERT INTO vouchers (code, nominal, valid_until, issued_sale_id)
               VALUES (?, ?, ?, ?)""",
            (code, nominal, valid_until, sale_id)
        )
        voucher_id = cur.lastrowid

        cur.execute(
            """INSERT INTO sale_items (sale_id, voucher_id, quantity,
                                       cost_price, sale_price)
               VALUES (?, ?, 1, 0, ?)""",
            (sale_id, voucher_id, nominal)
        )

        conn.commit()
        return True, {"code": code, "nominal": nominal,
                      "valid_until": valid_until, "sale_id": sale_id}

    except Exception as e:
        conn.rollback()
        return False, f"Грешка при издаване на ваучер: {e}"
    finally:
        conn.close()


def get_all_vouchers(status=None):
    """
    Връща всички ваучери, опционално филтрирани по статус.
    Динамично обновява 'Изтекъл' за активни ваучери с изтекъл срок —
    така списъкът винаги показва вярната картина, без отделен крон.
    """
    conn = get_connection()

    # Първо: маркираме изтеклите. Активни ваучери, чийто срок е минал,
    # стават 'Изтекъл'. Това е "ленивата" актуализация — става при четене,
    # не на заден план. За мащаб на книжарница е напълно достатъчно.
    conn.execute(
        """UPDATE vouchers
           SET status = 'Изтекъл'
           WHERE status = 'Активен'
             AND valid_until IS NOT NULL
             AND date(valid_until) < date('now', 'localtime')"""
    )
    conn.commit()

    # После: четем списъка.
    query = "SELECT * FROM vouchers"
    params = []
    if status is not None:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY issued_at DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def find_voucher_by_code(code):
    """Намира ваучер по код. Връща речник или None.
    Ползва се в ПОС-а, когато клиентът дава ваучер за плащане."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM vouchers WHERE code = ?", (code.strip(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def validate_voucher_for_use(code):
    """
    Проверява дали ваучер с дадения код може да се ползва.
    Връща (True, voucher_dict) ако да, или (False, грешка) ако не.
    """
    voucher = find_voucher_by_code(code)
    if voucher is None:
        return False, f"Ваучер с код „{code}“ не съществува."
    if voucher["status"] == "Използван":
        return False, f"Ваучер „{code}“ вече е използван на {voucher['used_at']}."
    if voucher["status"] == "Изтекъл":
        return False, f"Ваучер „{code}“ е изтекъл на {voucher['valid_until']}."
    # Допълнителна проверка — макар че get_all_vouchers ленивото обновява,
    # find_voucher_by_code не го прави, затова сверяваме и тук.
    from datetime import date
    if voucher["valid_until"] and voucher["valid_until"] < date.today().isoformat():
        return False, f"Ваучер „{code}“ е изтекъл на {voucher['valid_until']}."
    return True, voucher


