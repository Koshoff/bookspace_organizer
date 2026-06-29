from db.connection import get_connection
# само АКО функцията хваща sqlite3.IntegrityError:
import sqlite3


# ---------- ПРОДАЖБИ / ПОС (Модул 4) ----------

def get_current_stock(product_id):
    """Връща текущата наличност на една книга — сборът на движенията ѝ."""
    conn = get_connection()
    row = conn.execute(
        """SELECT COALESCE(SUM(quantity_change), 0) AS stock
           FROM stock_movements WHERE product_id = ?""",
        (product_id,)
    ).fetchone()
    conn.close()
    return row["stock"]


def create_sale(order_number, waybill_number, items, payment_method, invoice_data=None, operator="система"):
    """
    Създава цяла продажба в една транзакция: капак + редове + движения (с МИНУС).
    Проверява наличност ПРЕДИ да продаде — ако не стига, отказва всичко.

    'items' е списък от речници с: product_id, title, quantity, cost_price, sale_price.
    'invoice_data' е None или речник с данните за фактура.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        # --- ПРОВЕРКА НА НАЛИЧНОСТ за всяка книга, ПРЕДИ да пипаме нещо ---
        for item in items:
            row = cur.execute(
                """SELECT COALESCE(SUM(quantity_change), 0) AS stock
                   FROM stock_movements WHERE product_id = ?""",
                (item["product_id"],)
            ).fetchone()
            if row["stock"] < item["quantity"]:
                # Не стига наличност → отказваме ЦЯЛАТА продажба.
                conn.rollback()
                return False, (f"Недостатъчна наличност за „{item['title']}“ "
                               f"(налични: {row['stock']}, искани: {item['quantity']}).")

        # --- 1. КАПАКЪТ ---
        if invoice_data:
            cur.execute(
                """INSERT INTO sales
                   (order_number, waybill_number, payment_method, invoice_issued,
                    invoice_number, buyer_company, buyer_eik, buyer_mol,
                    buyer_address, buyer_email)
                   VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?)""",
                (order_number, waybill_number, payment_method,
                 invoice_data["invoice_number"], invoice_data["buyer_company"],
                 invoice_data["buyer_eik"], invoice_data["buyer_mol"],
                 invoice_data["buyer_address"], invoice_data["buyer_email"])
            )
        else:
            cur.execute(
                """INSERT INTO sales (order_number, waybill_number, payment_method)
                   VALUES (?, ?, ?)""",
                (order_number, waybill_number, payment_method)
            )
        sale_id = cur.lastrowid

        # --- 2. РЕДОВЕТЕ + ДВИЖЕНИЯТА (с МИНУС) ---
        for item in items:
            cur.execute(
                """INSERT INTO sale_items
                   (sale_id, product_id, quantity, cost_price, sale_price)
                   VALUES (?, ?, ?, ?, ?)""",
                (sale_id, item["product_id"], item["quantity"],
                 item["cost_price"], item["sale_price"])
            )
            # МИНУС количество — изходяща стока.
            cur.execute(
                """INSERT INTO stock_movements
                   (product_id, movement_type, quantity_change, document_ref, operator)
                   VALUES (?, 'Продажба', ?, ?, ?)""",
                (item["product_id"], -item["quantity"],
                 f"Поръчка №{order_number}", operator)
            )

        conn.commit()
        return True, f"Продажба №{order_number} е записана успешно."

    except Exception as e:
        conn.rollback()
        return False, f"Грешка при записа: {e}"
    finally:
        conn.close()


def get_product_for_sale(isbn):
    """Връща данните на книга по ISBN за продажба, ВКЛ. доставна цена и наличност.
    Доставната цена я взимаме от последната доставка на тази книга."""
    conn = get_connection()
    row = conn.execute(
        """SELECT p.id, p.isbn, p.title, p.author, p.cover_price,
                  s.name AS supplier_name,
                  COALESCE((SELECT SUM(quantity_change) FROM stock_movements m
                            WHERE m.product_id = p.id), 0) AS stock,
                  COALESCE((SELECT di.delivery_price FROM delivery_items di
                            WHERE di.product_id = p.id
                            ORDER BY di.id DESC LIMIT 1), 0) AS last_cost
           FROM products p
           JOIN suppliers s ON s.id = p.supplier_id
           WHERE p.isbn = ?""",
        (isbn,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------- ЖУРНАЛ НА ПРОДАЖБИТЕ (Модул 5) ----------

def get_sales(status=None, date_from=None, date_to=None):
    """
    Връща продажбите с обобщени доставна/продажна суми, с опционални филтри.
    Печалбата се смята после, в Python, от двете суми.
    Същият модел на динамична WHERE клауза като при доставките.
    """
    conn = get_connection()
    query = """
        SELECT
            s.id,
            s.created_at,
            s.order_number,
            s.waybill_number,
            s.status,
            s.payment_date,
            s.payment_method,
            s.supplementary_payment_method,
            s.supplementary_amount,
            s.invoice_issued,
            COALESCE(SUM(si.quantity * si.cost_price), 0) AS total_cost,
            COALESCE(SUM(si.quantity * si.sale_price), 0) AS total_sale
        FROM sales s
        LEFT JOIN sale_items si ON si.sale_id = s.id
    """
    conditions, params = [], []

    if status is not None:
        conditions.append("s.status = ?")
        params.append(status)
    if date_from is not None:
        # Филтрираме по created_at (датата на самата продажба).
        # date() отрязва часа, за да сравняваме само по ден.
        conditions.append("date(s.created_at) >= ?")
        params.append(date_from)
    if date_to is not None:
        conditions.append("date(s.created_at) <= ?")
        params.append(date_to)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " GROUP BY s.id ORDER BY s.created_at DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def set_sale_status(sale_id, new_status):
    """Сменя статуса на продажба. При 'Платена' записва timestamp в payment_date."""
    conn = get_connection()
    try:
        if new_status == "Платена":
            conn.execute(
                """UPDATE sales
                   SET status = 'Платена',
                       payment_date = datetime('now', 'localtime')
                   WHERE id = ?""",
                (sale_id,)
            )
        else:
            # При други статуси изчистваме payment_date (вече не е платена).
            conn.execute(
                "UPDATE sales SET status = ?, payment_date = NULL WHERE id = ?",
                (new_status, sale_id)
            )
        conn.commit()
        return True
    finally:
        conn.close()


def get_sold_books_for_reorder(date_from, date_to):
    """За експорта: всички продадени книги в периода, групирани по доставчик.
    Сумира количествата на една и съща книга през всички продажби в периода."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT
               sup.name AS supplier_name,
               p.isbn,
               p.title,
               p.author,
               SUM(si.quantity) AS total_sold
           FROM sale_items si
           JOIN sales s   ON s.id = si.sale_id
           JOIN products p ON p.id = si.product_id
           JOIN suppliers sup ON sup.id = p.supplier_id
           WHERE date(s.created_at) >= ? AND date(s.created_at) <= ?
           GROUP BY p.id
           ORDER BY sup.name, p.title""",
        (date_from, date_to)
    ).fetchall()
    conn.close()
    return rows

def get_daily_supplier_reorders(day):
    """
    Връща продадените КНИГИ за конкретен ден (формат 'YYYY-MM-DD'), с доставчик
    и неговия имейл, за автоматичните заявки за зареждане.

    - Изключва отказани продажби (сторното връща стоката — не я презареждаме).
    - Изключва ваучерни редове (product_id IS NULL).
    - Сумира едно и също заглавие през всички продажби за деня.
    Подредено по доставчик, после по заглавие — готово за групиране в UI.
    """
    conn = get_connection()
    rows = conn.execute(
        """SELECT
               sup.id    AS supplier_id,
               sup.name  AS supplier_name,
               sup.email AS supplier_email,
               p.isbn,
               p.title,
               p.author,
               SUM(si.quantity) AS total_sold
           FROM sale_items si
           JOIN sales s     ON s.id = si.sale_id
           JOIN products p  ON p.id = si.product_id
           JOIN suppliers sup ON sup.id = p.supplier_id
           WHERE date(s.created_at) = ?
             AND s.status != 'Отказана'
             AND si.product_id IS NOT NULL
           GROUP BY p.id
           ORDER BY sup.name, p.title""",
        (day,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_sale_with_voucher(order_number, waybill_number, items, voucher_id,
                             supplementary_method=None, invoice_data=None,
                             operator="система"):
    """
    Продажба с ваучер. Ако сумата надвишава номинала, supplementary_method
    се ползва за разликата (Сценарий А — един метод на доплащане).
    Ако сумата е <= номинала, supplementary_method се игнорира.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        # Проверка на наличност (както преди).
        for item in items:
            row = cur.execute(
                """SELECT COALESCE(SUM(quantity_change), 0) AS stock
                   FROM stock_movements WHERE product_id = ?""",
                (item["product_id"],)
            ).fetchone()
            if row["stock"] < item["quantity"]:
                conn.rollback()
                return False, (f"Недостатъчна наличност за „{item['title']}“ "
                               f"(налични: {row['stock']}).")

        # Проверка на ваучера в транзакцията (race safety).
        v_row = cur.execute(
            "SELECT * FROM vouchers WHERE id = ? AND status = 'Активен'",
            (voucher_id,)
        ).fetchone()
        if v_row is None:
            conn.rollback()
            return False, "Ваучерът вече не е активен."

        # Изчисляваме сумата и доплащането.
        total_sale = sum(i["quantity"] * i["sale_price"] for i in items)
        nominal = v_row["nominal"]
        supplement_amount = 0.0

        if total_sale > nominal:
            # Доплащане задължително — трябва да е избран метод.
            if not supplementary_method:
                conn.rollback()
                return False, ("Сумата надвишава номинала на ваучера. "
                               "Изберете метод на доплащане.")
            supplement_amount = round(total_sale - nominal, 2)

        # Капак на продажбата. payment_method = 'Ваучер', плюс полетата за
        # доплащане, ако има. Ако няма — supplementary_amount = 0 и метод NULL.
        if invoice_data:
            cur.execute(
                """INSERT INTO sales (order_number, waybill_number, payment_method,
                                      supplementary_payment_method, supplementary_amount,
                                      invoice_issued, invoice_number, buyer_company,
                                      buyer_eik, buyer_mol, buyer_address, buyer_email)
                   VALUES (?, ?, 'Ваучер', ?, ?, 1, ?, ?, ?, ?, ?, ?)""",
                (order_number, waybill_number,
                 supplementary_method if supplement_amount > 0 else None,
                 supplement_amount,
                 invoice_data["invoice_number"], invoice_data["buyer_company"],
                 invoice_data["buyer_eik"], invoice_data["buyer_mol"],
                 invoice_data["buyer_address"], invoice_data["buyer_email"])
            )
        else:
            cur.execute(
                """INSERT INTO sales (order_number, waybill_number, payment_method,
                                      supplementary_payment_method, supplementary_amount)
                   VALUES (?, ?, 'Ваучер', ?, ?)""",
                (order_number, waybill_number,
                 supplementary_method if supplement_amount > 0 else None,
                 supplement_amount)
            )
        sale_id = cur.lastrowid

        # Редове + движения (същото като преди).
        for item in items:
            cur.execute(
                """INSERT INTO sale_items (sale_id, product_id, quantity,
                                           cost_price, sale_price)
                   VALUES (?, ?, ?, ?, ?)""",
                (sale_id, item["product_id"], item["quantity"],
                 item["cost_price"], item["sale_price"])
            )
            cur.execute(
                """INSERT INTO stock_movements (product_id, movement_type,
                                                quantity_change, document_ref, operator)
                   VALUES (?, 'Продажба', ?, ?, ?)""",
                (item["product_id"], -item["quantity"],
                 f"Поръчка №{order_number} (ваучер)", operator)
            )

        # Маркираме ваучера използван.
        cur.execute(
            """UPDATE vouchers
               SET status = 'Използван',
                   used_at = datetime('now', 'localtime'),
                   used_sale_id = ?
               WHERE id = ?""",
            (sale_id, voucher_id)
        )

        conn.commit()
        if supplement_amount > 0:
            return True, (f"Продажба №{order_number} записана. "
                          f"Ваучер: {nominal:.2f} лв. + доплащане "
                          f"{supplement_amount:.2f} лв. с „{supplementary_method}“.")
        else:
            return True, f"Продажба №{order_number} записана (плащане с ваучер)."

    except Exception as e:
        conn.rollback()
        return False, f"Грешка при записа: {e}"
    finally:
        conn.close()  