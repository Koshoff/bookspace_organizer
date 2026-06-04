from db.connection import get_connection
# само АКО функцията хваща sqlite3.IntegrityError:
import sqlite3


# ---------- ГЛАВНО КОМАНДНО ТАБЛО (Модул 0) ----------

def get_dashboard_data(date_from, date_to, payment_method=None):
    """
    Връща всички данни за командното табло за зададения период.
    date_from / date_to са низове 'YYYY-MM-DD'.

    ВАЖНО за филтрирането по дата:
    - Приходите (платени продажби) се филтрират по payment_date (кога е платено).
    - Разходите (платени доставки) се филтрират по delivery_paid_date (кога сме платили).
    Така и двете страни гледат КОГА реално са минали парите.
    """
    conn = get_connection()

    # --- КАРТА 1: Приходи = платени продажби, по дата на плащане ---
    rev_query = """SELECT COALESCE(SUM(si.quantity * si.sale_price), 0) AS total
                   FROM sales s
                   JOIN sale_items si ON si.sale_id = s.id
                   WHERE s.status = 'Платена'
                     AND date(s.payment_date) >= ? AND date(s.payment_date) <= ?"""
    rev_params = [date_from, date_to]
    if payment_method:
        rev_query += " AND s.payment_method = ?"
        rev_params.append(payment_method)
    revenue = conn.execute(rev_query, rev_params).fetchone()["total"]

    # COGS — доставна стойност на продадените (платени) книги за периода.
    # Разходът се отчита, когато книгата напуска склада чрез продажба, не при доставка.
    cogs = conn.execute(
        """SELECT COALESCE(SUM(si.quantity * si.cost_price), 0) AS total
           FROM sale_items si
           JOIN sales s ON s.id = si.sale_id
           WHERE s.status = 'Платена'
             AND si.product_id IS NOT NULL
             AND date(s.created_at) >= ? AND date(s.created_at) <= ?""",
        (date_from, date_to)
    ).fetchone()["total"]

    # Оперативни разходи за периода (наем, заплати, реклама и т.н.) —
    # филтрират се по date (датата на издаване на разхода).
    from db.expenses import get_expenses_total_by_period
    operating_total = get_expenses_total_by_period(date_from, date_to)

    # Разходи за реклама и маркетинг за периода — за KPI „CAC".
    # Същата таблица operating_expenses, само филтрирана по категория.
    ad_spend = conn.execute(
        """SELECT COALESCE(SUM(amount), 0) AS total
           FROM operating_expenses
           WHERE category = 'Реклама и Маркетинг'
             AND date >= ? AND date <= ?""",
        (date_from, date_to)
    ).fetchone()["total"]

    # Общ брой продадени физически бройки за периода — за „Средна цена на бройка".
    # Не на поръчки, а на индивидуални артикули.
    total_units_sold = conn.execute(
        """SELECT COALESCE(SUM(si.quantity), 0) AS total
           FROM sale_items si
           JOIN sales s ON s.id = si.sale_id
           WHERE s.status = 'Платена'
             AND si.product_id IS NOT NULL
             AND date(s.payment_date) >= ? AND date(s.payment_date) <= ?""",
        (date_from, date_to)
    ).fetchone()["total"]

    # Общите разходи = COGS + оперативни. Това отива в картата „Общо разходи".
    expenses = cogs + operating_total

    # --- КАРТА 4: Брой продажби за периода (по дата на създаване, не отказани) ---
    sales_count = conn.execute(
        """SELECT COUNT(*) AS c
           FROM sales
           WHERE date(created_at) >= ? AND date(created_at) <= ?
             AND status != 'Отказана'""",
        (date_from, date_to)
    ).fetchone()["c"]

    # --- ЛЯВА КОЛОНА: Задължения — неплатени доставки (най-новите отгоре) ---
    # Тези НЕ се филтрират по период — дължиш ги СЕГА, независимо кога са вкарани.
    liabilities = conn.execute(
        """SELECT d.id, d.doc_type, d.doc_number, d.doc_date, s.name AS supplier_name,
                  COALESCE(SUM(di.quantity * di.delivery_price), 0) AS amount
           FROM deliveries d
           JOIN suppliers s ON s.id = d.supplier_id
           LEFT JOIN delivery_items di ON di.delivery_id = d.id
           WHERE d.payment_status = 'Неплатена'
           GROUP BY d.id
           ORDER BY d.doc_date DESC"""
    ).fetchall()

    # --- ДЯСНА КОЛОНА: Вземания — продажби, чакащи плащане (наложен платеж) ---
    receivables = conn.execute(
        """SELECT s.id, s.order_number, s.waybill_number, s.created_at,
                  COALESCE(SUM(si.quantity * si.sale_price), 0) AS amount
           FROM sales s
           LEFT JOIN sale_items si ON si.sale_id = s.id
           WHERE s.status = 'Чака плащане'
           GROUP BY s.id
           ORDER BY s.created_at DESC"""
    ).fetchall()

    # --- ДОЛЕН ПАНЕЛ: последни 10 активности (смесено от трите вида) ---
    # UNION ALL слепва три заявки в общ списък. Всяка дава еднакви колони:
    # дата, тип, документ, стойност — за да се подредят заедно по време.
    activities = conn.execute(
        """SELECT * FROM (
               -- Продажби
               SELECT s.created_at AS ts,
                      CASE
                          WHEN s.order_number LIKE 'VOUCHER-%' THEN 'Издаване ваучер'
                          WHEN s.payment_method = 'Ваучер' THEN 'Продажба (с ваучер)'
                          ELSE 'Продажба'
                      END AS type,
                      'Поръчка №' || COALESCE(s.order_number, '-') AS doc,
                      COALESCE((SELECT SUM(si.quantity * si.sale_price)
                                FROM sale_items si WHERE si.sale_id = s.id), 0) AS value
               FROM sales s

               UNION ALL

               -- Доставки
               SELECT d.created_at AS ts, 'Доставка' AS type,
                      d.doc_type || ' №' || d.doc_number AS doc,
                      COALESCE((SELECT SUM(di.quantity * di.delivery_price)
                                FROM delivery_items di WHERE di.delivery_id = d.id), 0) AS value
               FROM deliveries d

               UNION ALL

               -- Кредитни известия
               SELECT cn.created_at AS ts, 'Кредитно известие' AS type,
                      'Бележка №' || cn.original_receipt AS doc,
                      cn.returned_amount AS value
               FROM credit_notes cn
           )
           ORDER BY ts DESC
           LIMIT 10"""
    ).fetchall()

    conn.close()

    return {
        "revenue": revenue,
        "expenses": expenses,                # сборът: COGS + оперативни
        "cogs": cogs,                        # отделна разбивка за UI
        "operating_expenses": operating_total, # отделна разбивка за UI
        "profit": revenue - expenses,        # Карта 3: чиста печалба (може и да е минус)
        "sales_count": sales_count,
        "ad_spend": ad_spend,                    
        "total_units_sold": total_units_sold,
        "liabilities": liabilities,
        "receivables": receivables,
        "activities": activities,
    }








