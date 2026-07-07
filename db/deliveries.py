from db.connection import get_connection
# само АКО функцията хваща sqlite3.IntegrityError:
import sqlite3


# ---------- ДОСТАВКИ (Модул 3) ----------

def create_delivery(supplier_id, doc_type, doc_number, doc_date, items, payment_type,
                    operator="система", invoice_file_path=None):
    """
    Създава ЦЯЛА доставка в една транзакция: капак + редове + складови движения.
    'items' е списък от речници, всеки с: product_id, quantity, settlement_type,
    supplier_percent, delivery_price.

    Принцип: или всичко минава, или нищо. Затова няма commit по средата —
    само един commit накрая, и rollback при всяка грешка.

    ВАЖНО (контрол вместо тихо презаписване): историческите last_delivery_price
    и last_discount_pct се обновяват ЕДВА ТУК — при финалния запис на доставката,
    не при въвеждане/сканиране. Така картонът пази цената до потвърждение.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        # --- 1. КАПАКЪТ: редът в deliveries ---
        cur.execute(
            """INSERT INTO deliveries (supplier_id, doc_type, doc_number, doc_date,
                                       payment_type, invoice_file_path)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (supplier_id, doc_type, doc_number, doc_date, payment_type,
             invoice_file_path)
        )
        # lastrowid ни дава id-то на МЕЖДУ САМО ВКАРАНИЯ ред — трябва ни,
        # за да вържем редовете и движенията към ТАЗИ доставка.
        delivery_id = cur.lastrowid

        # --- 2. РЕДОВЕТЕ + ДВИЖЕНИЯТА за всяка книга ---
        for item in items:
            # 2а. Ред в delivery_items
            cur.execute(
                """INSERT INTO delivery_items
                   (delivery_id, product_id, quantity, settlement_type,
                    supplier_percent, delivery_price)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (delivery_id, item["product_id"], item["quantity"],
                 item["settlement_type"], item["supplier_percent"],
                 item["delivery_price"])
            )

            # 2б. Движение на склада: +количество (входяща стока).
            # ЕТО КЪДЕ наличността реално се вдига над нулата.
            cur.execute(
                """INSERT INTO stock_movements
                   (product_id, movement_type, quantity_change, document_ref, operator)
                   VALUES (?, 'Доставка', ?, ?, ?)""",
                (item["product_id"], item["quantity"],
                 f"{doc_type} №{doc_number}", operator)
            )

            # 2в. Обновяваме историческата доставна цена/отстъпка на картона —
            # само сега, при потвърден запис. Това е „контрольорът".
            cur.execute(
                """UPDATE products
                   SET last_delivery_price = ?, last_discount_pct = ?
                   WHERE id = ?""",
                (item["delivery_price"], item.get("supplier_percent"),
                 item["product_id"])
            )

        # --- 3. ЕДИН commit за всичко наведнъж ---
        conn.commit()
        return True, f"Доставка №{doc_number} е записана успешно."

    except Exception as e:
        # Нещо се счупи по средата → връщаме базата в изходно положение.
        conn.rollback()
        return False, f"Грешка при записа: {e}"
    finally:
        conn.close()




def get_deliveries(supplier_id=None, payment_status=None, date_from=None, date_to=None, payment_type=None):
    """
    Връща доставки (капаците) с име на доставчик и обща сума, с опционални филтри.
    Всеки филтър е None, ако не е зададен — тогава не стеснява.
    Това е модел, който ще повтаряме: динамично сглобена WHERE клауза.
    """
    conn = get_connection()

    # Започваме с базова заявка и трупаме условия според подадените филтри.
    query = """
        SELECT
            d.id,
            d.doc_type,
            d.doc_number,
            d.doc_date,
            d.payment_status,
            d.delivery_paid_date,
            s.name AS supplier_name,
            d.payment_type,
            d.invoice_file_path,
            COALESCE(SUM(di.quantity * di.delivery_price), 0) AS total_amount
        FROM deliveries d
        JOIN suppliers s ON s.id = d.supplier_id
        LEFT JOIN delivery_items di ON di.delivery_id = d.id
    """
    conditions = []   # тук трупаме условията
    params = []       # и съответните стойности (пак параметризирано, не слепено!)

    if supplier_id is not None:
        conditions.append("d.supplier_id = ?")
        params.append(supplier_id)
    if payment_status is not None:
        conditions.append("d.payment_status = ?")
        params.append(payment_status)
    if date_from is not None:
        conditions.append("d.doc_date >= ?")
        params.append(date_from)
    if date_to is not None:
        conditions.append("d.doc_date <= ?")
        params.append(date_to)
    if payment_type is not None:
        conditions.append("d.payment_type = ?")
        params.append(payment_type)

    # Ако има условия, лепим ги с WHERE ... AND ...
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    # GROUP BY е нужен заради SUM — групираме редовете по доставка.
    query += " GROUP BY d.id ORDER BY d.doc_date DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def mark_delivery_paid(delivery_id):
    """Маркира доставка като платена И записва точния момент в delivery_paid_date.
    Това е изискването ти за автоматичния timestamp."""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE deliveries
               SET payment_status = 'Платена',
                   delivery_paid_date = datetime('now', 'localtime')
               WHERE id = ?""",
            (delivery_id,)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_delivery_items(delivery_id):
    """Връща книгите в конкретна доставка — за детайлния изглед при клик."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT p.isbn, p.title, di.quantity, di.settlement_type,
                  di.supplier_percent, di.delivery_price
           FROM delivery_items di
           JOIN products p ON p.id = di.product_id
           WHERE di.delivery_id = ?""",
        (delivery_id,)
    ).fetchall()
    conn.close()
    return rows


def get_delivery_payment_breakdown(date_from=None, date_to=None):
    """
    Връща разбивка на доставките по начин на плащане за периода:
    за всеки тип — обща сума и брой документи. Ползва се за счетоводния
    брояч в журнала и за разбивката в таблото.
    """
    conn = get_connection()
    query = """
        SELECT
            d.payment_type,
            COUNT(DISTINCT d.id) AS doc_count,
            COALESCE(SUM(di.quantity * di.delivery_price), 0) AS total
        FROM deliveries d
        LEFT JOIN delivery_items di ON di.delivery_id = d.id
    """
    conditions, params = [], []
    if date_from is not None:
        conditions.append("date(d.doc_date) >= ?")
        params.append(date_from)
    if date_to is not None:
        conditions.append("date(d.doc_date) <= ?")
        params.append(date_to)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " GROUP BY d.payment_type"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    # Връщаме речник {тип: {count, total}} за лесен достъп.
    return {r["payment_type"]: {"count": r["doc_count"], "total": r["total"]} for r in rows}