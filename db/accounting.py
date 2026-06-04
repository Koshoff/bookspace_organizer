from db.connection import get_connection
# само АКО функцията хваща sqlite3.IntegrityError:
import sqlite3


# ---------- СЧЕТОВОДЕН ЕКСПОРТ И ДДС (Модул счетоводство) ----------

def get_sales_journal(date_from, date_to):
    """
    Дневник на ПРОДАЖБИТЕ за ДДС.
    - Книги: 9% ДДС, основа = сума/1.09, ДДС = сума - основа.
    - Ваучери (продажба на ваучер): 0% ДДС, основа = сума, ДДС = 0.
      Различаваме по това дали редът има voucher_id вместо product_id.
    - Кредитните известия влизат отделно с минус, по своята дата.
    """
    conn = get_connection()

    # Продажбите без отказани/чакащи. Сега вадим и какво е плащането.
    sales = conn.execute(
        """SELECT
               s.id AS sale_id,
               s.created_at,
               s.order_number,
               s.invoice_number,
               s.payment_method,
               s.supplementary_payment_method,
               s.supplementary_amount
           FROM sales s
           WHERE s.status = 'Платена'
             AND date(s.created_at) >= ? AND date(s.created_at) <= ?
           ORDER BY s.created_at""",
        (date_from, date_to)
    ).fetchall()

    journal = []

    # За всяка продажба теглим редовете отделно — за да различим ваучерни от книжни.
    for s in sales:
        rows = conn.execute(
            """SELECT product_id, voucher_id, quantity, sale_price
               FROM sale_items WHERE sale_id = ?""",
            (s["sale_id"],)
        ).fetchall()

        # Разделяме на две групи суми: книжна (9%) и ваучерна (0%).
        book_total = 0.0
        voucher_total = 0.0
        for r in rows:
            line_total = r["quantity"] * r["sale_price"]
            if r["voucher_id"] is not None:
                # Ред-ваучер — 0% ДДС, група Д.
                voucher_total += line_total
            else:
                # Ред-книга — 9% ДДС, група Б.
                book_total += line_total

        # Описание на плащането — ясно за счетоводителя.
        if s["payment_method"] == "Ваучер" and s["supplementary_amount"] > 0:
            pay_desc = (f"Ваучер + {s['supplementary_payment_method']} "
                        f"({s['supplementary_amount']:.2f} лв.)")
        else:
            pay_desc = s["payment_method"]

        # Книжната част (ако има) — отделен ред в дневника с 9% ДДС.
        if book_total > 0:
            base = round(book_total / 1.09, 2)
            vat = round(book_total - base, 2)
            journal.append({
                "Документ": s["invoice_number"] or f"Поръчка №{s['order_number'] or '-'}",
                "Данъчна основа": base,
                "ДДС ставка": "9%",
                "Начислено ДДС": vat,
                "Обща стойност с ДДС": round(book_total, 2),
                "Фискална група": "Б",
                "Тип плащане": pay_desc,
                "Статус": "Продажба (книги)",
            })

        # Ваучерната част (ако има) — отделен ред с 0% ДДС, група Д.
        if voucher_total > 0:
            journal.append({
                "Документ": f"Издаване ваучер: {s['order_number'] or '-'}",
                "Данъчна основа": round(voucher_total, 2),
                "ДДС ставка": "0%",
                "Начислено ДДС": 0.0,
                "Обща стойност с ДДС": round(voucher_total, 2),
                "Фискална група": "Д",
                "Тип плащане": pay_desc,
                "Статус": "Продажба (ваучер)",
            })

    # Кредитните известия — по тяхната дата, с минус, както преди.
    credits = conn.execute(
        """SELECT cn.created_at, cn.original_receipt, cn.returned_amount,
                  s.payment_method
           FROM credit_notes cn
           JOIN sales s ON s.id = cn.sale_id
           WHERE date(cn.created_at) >= ? AND date(cn.created_at) <= ?
           ORDER BY cn.created_at""",
        (date_from, date_to)
    ).fetchall()

    for c in credits:
        total = -c["returned_amount"]
        base = round(total / 1.09, 2)
        vat = round(total - base, 2)
        journal.append({
            "Документ": f"КИ към бележка №{c['original_receipt']}",
            "Данъчна основа": base,
            "ДДС ставка": "9%",
            "Начислено ДДС": vat,
            "Обща стойност с ДДС": round(total, 2),
            "Фискална група": "Б",
            "Тип плащане": c["payment_method"],
            "Статус": "Кредитно известие",
        })

    conn.close()
    return journal


def get_purchases_journal(date_from, date_to):
    """
    Дневник на ПОКУПКИТЕ (доставки от издателства), филтриран по дата на ПЛАЩАНЕ.
    Само платените доставки, защото дневникът на покупките отразява платените фактури.
    """
    conn = get_connection()
    rows = conn.execute(
        """SELECT
               d.id,
               d.doc_number,
               d.delivery_paid_date,
               sup.name AS supplier_name,
               COALESCE(SUM(di.quantity * di.delivery_price), 0) AS total_with_vat
           FROM deliveries d
           JOIN suppliers sup ON sup.id = d.supplier_id
           LEFT JOIN delivery_items di ON di.delivery_id = d.id
           WHERE d.payment_status = 'Платена'
             AND date(d.delivery_paid_date) >= ? AND date(d.delivery_paid_date) <= ?
           GROUP BY d.id
           ORDER BY d.delivery_paid_date""",
        (date_from, date_to)
    ).fetchall()
    conn.close()

    journal = []
    for r in rows:
        total = r["total_with_vat"]
        base = round(total / 1.09, 2)
        vat = round(total - base, 2)
        journal.append({
            "Фактура доставчик": r["doc_number"],
            "Доставчик": r["supplier_name"],
            "Данъчна основа": base,
            "ДДС 9%": vat,
            "Общо платена сума": round(total, 2),
        })
    return journal


def get_consignment_report(date_from, date_to):
    """
    Отчет за продадена КОНСИГНАЦИЯ, групиран по издателство.
    Правило: консигнацията се продава ПЪРВА. Затова за всяка книга
    продадените бройки се отчитат като консигнационни до размера на
    реално доставените консигнационни бройки (не повече).

    Работи на ниво "обща бройка за книга", което е достатъчно за отчета
    към издателството (колко им дължим за периода).
    """
    conn = get_connection()
    rows = conn.execute(
        """
        WITH
        -- Колко КОНСИГНАЦИОННИ бройки са доставени за всяка книга (общо, за всички време).
        consigned AS (
            SELECT product_id, SUM(quantity) AS consigned_qty
            FROM delivery_items
            WHERE settlement_type = 'Консигнация'
            GROUP BY product_id
        ),
        -- Колко са ПРОДАДЕНИ за периода (без отказани), за всяка книга.
        sold AS (
            SELECT si.product_id,
                   SUM(si.quantity) AS sold_qty,
                   -- средни цени, за да смятаме дължимо и марж на бройка
                   AVG(si.cost_price) AS avg_cost,
                   AVG(si.sale_price) AS avg_sale
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            WHERE s.status != 'Отказана'
              AND date(s.created_at) >= ? AND date(s.created_at) <= ?
            GROUP BY si.product_id
        )
        SELECT
            sup.name AS supplier_name,
            -- Консигнационни продадени = по-малкото от (продадени, доставени консигнация).
            -- MIN гарантира правилото "не повече от реално доставените консигнационни".
            SUM(MIN(sold.sold_qty, consigned.consigned_qty)) AS sold_qty,
            -- Дължимо към издателството: консигнационни продадени × доставна цена.
            SUM(MIN(sold.sold_qty, consigned.consigned_qty) * sold.avg_cost) AS owed_to_publisher,
            -- Марж на книжарницата върху тези консигнационни бройки.
            SUM(MIN(sold.sold_qty, consigned.consigned_qty) * (sold.avg_sale - sold.avg_cost)) AS bookstore_margin
        FROM sold
        JOIN consigned ON consigned.product_id = sold.product_id
        JOIN products p ON p.id = sold.product_id
        JOIN suppliers sup ON sup.id = p.supplier_id
        GROUP BY sup.id
        ORDER BY sup.name
        """,
        (date_from, date_to)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ---------- ГЕНЕРИРАНЕ НА EXCEL ДНЕВНИК ----------

def build_monthly_payment_excel(year_month):
    """Excel с три листа: 'Неплатени', 'Платени', 'Оперативни Разходи' за месеца."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from io import BytesIO
    from db.expenses import get_expenses_by_period

    data = get_monthly_payment_report(year_month)
    wb = Workbook()

    # --- ЛИСТ 1: НЕПЛАТЕНИ ---
    ws = wb.active
    ws.title = "Неплатени"
    ws.append(["Дата/Час", "Поръчка №", "Товарителница",
               "Начин на плащане", "Сума"])
    for c in ws[1]:
        c.font = Font(bold=True)
    row = 2
    for r in data["unpaid"]:
        ws.append([
            r["created_at"],
            r["order_number"] or "-",
            r["waybill_number"] or "-",
            r["payment_method"],
            round(r["amount"], 2),
        ])
        row += 1
    if row > 2:
        ws.cell(row=row, column=1, value="ОБЩО ВИСЯЩИ").font = Font(bold=True)
        ws.cell(row=row, column=5, value=f"=SUM(E2:E{row-1})").font = Font(bold=True)

    # --- ЛИСТ 2: ПЛАТЕНИ ---
    ws2 = wb.create_sheet("Платени")
    ws2.append(["Дата/Час", "Поръчка №", "Товарителница",
                "Начин на плащане", "Сума", "Дата на плащане"])
    for c in ws2[1]:
        c.font = Font(bold=True)
    row = 2
    for r in data["paid"]:
        ws2.append([
            r["created_at"],
            r["order_number"] or "-",
            r["waybill_number"] or "-",
            r["payment_method"],
            round(r["amount"], 2),
            r["payment_date"],
        ])
        row += 1
    if row > 2:
        ws2.cell(row=row, column=1, value="ОБЩО СЪБРАНИ").font = Font(bold=True)
        ws2.cell(row=row, column=5, value=f"=SUM(E2:E{row-1})").font = Font(bold=True)

    # --- ЛИСТ 3: ОПЕРАТИВНИ РАЗХОДИ ---
    # Групирани по категория, после по дата в рамките на категорията.
    # Между категориите вкарваме междинна сума, за да види счетоводителят
    # колко общо е отишло за наем, колко за заплати и т.н.
    ws3 = wb.create_sheet("Оперативни Разходи")
    ws3.append(["Дата", "Категория", "Описание", "Сума", "Документ №"])
    for c in ws3[1]:
        c.font = Font(bold=True)

    # Изчисляваме границите на месеца от 'year_month' формат 'YYYY-MM'.
    year, month = year_month.split("-")
    date_from = f"{year}-{month}-01"
    # Последен ден на месеца — взимаме първия на следващия и махаме един ден.
    from datetime import date as _date, timedelta as _timedelta
    next_month = int(month) + 1
    next_year = int(year)
    if next_month == 13:
        next_month = 1
        next_year += 1
    date_to = (_date(next_year, next_month, 1) - _timedelta(days=1)).isoformat()

    expenses = get_expenses_by_period(date_from, date_to)

    # Групираме по категория. expenses вече идва подреден по date DESC,
    # но за листа предпочитаме категория-после-дата, затова сортираме наново.
    expenses_sorted = sorted(expenses, key=lambda e: (e["category"], e["date"]))

    row = 2
    first_row_of_category = row
    current_category = None
    grand_total_start = row

    for e in expenses_sorted:
        # Когато сменим категория, добавяме междинна сума за предишната.
        if current_category is not None and e["category"] != current_category:
            ws3.cell(row=row, column=2,
                     value=f"Общо: {current_category}").font = Font(bold=True, italic=True)
            ws3.cell(row=row, column=4,
                     value=f"=SUM(D{first_row_of_category}:D{row-1})"
                     ).font = Font(bold=True, italic=True)
            row += 1
            first_row_of_category = row

        ws3.append([
            e["date"],
            e["category"],
            e["description"] or "-",
            round(e["amount"], 2),
            e["document_number"] or "-",
        ])
        current_category = e["category"]
        row += 1

    # След последния запис, междинна сума за последната категория.
    if current_category is not None:
        ws3.cell(row=row, column=2,
                 value=f"Общо: {current_category}").font = Font(bold=True, italic=True)
        ws3.cell(row=row, column=4,
                 value=f"=SUM(D{first_row_of_category}:D{row-1})"
                 ).font = Font(bold=True, italic=True)
        row += 1

    # Финален общ сбор — само за реалните данни, не за междинните суми.
    # Затова сумираме поредицата от D2:D{последен_ред}, но с филтър.
    # По-просто решение: записваме директна формула SUMIF за категория != "Общо:..."
    # Или: пазим списък от редове, които са истински данни.
    # За простота — сумираме директните стойности от Python (не формула).
    if expenses_sorted:
        total = sum(e["amount"] for e in expenses_sorted)
        ws3.cell(row=row+1, column=2, value="ОБЩО ЗА МЕСЕЦА").font = Font(bold=True, size=12)
        ws3.cell(row=row+1, column=4, value=round(total, 2)).font = Font(bold=True, size=12)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()  


def build_accounting_excel(date_from, date_to):
    """
    Връща Excel файл (в паметта, като bytes) с два листа:
    'Продажби' и 'Покупки'. Сумите с ДДС са стойности; основата и ДДС
    са Excel ФОРМУЛИ, за да е документът проверим и преизчислим.
    Връща bytes, готови за st.download_button.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from io import BytesIO

    wb = Workbook()

    # --- ЛИСТ 1: ПРОДАЖБИ ---
    ws = wb.active
    ws.title = "Продажби"
    headers = ["Документ", "Данъчна основа", "ДДС ставка", "Начислено ДДС",
               "Обща стойност с ДДС", "Фискална група", "Тип плащане", "Статус"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    sales = get_sales_journal(date_from, date_to)
    row = 2
    for s in sales:
        total = s["Обща стойност с ДДС"]
        is_voucher = s["ДДС ставка"] == "0%"
        ws.cell(row=row, column=1, value=s["Документ"])
        if is_voucher:
            ws.cell(row=row, column=2, value=total)
            ws.cell(row=row, column=3, value="0%")
            ws.cell(row=row, column=4, value=0)
        else:
            ws.cell(row=row, column=2, value=f"=E{row}/1.09")
            ws.cell(row=row, column=3, value=s["ДДС ставка"])
            ws.cell(row=row, column=4, value=f"=E{row}-B{row}")
        ws.cell(row=row, column=5, value=total)
        ws.cell(row=row, column=6, value=s["Фискална група"])
        ws.cell(row=row, column=7, value=s["Тип плащане"])
        ws.cell(row=row, column=8, value=s["Статус"])
        row += 1

    if row > 2:
        ws.cell(row=row, column=1, value="ОБЩО").font = Font(bold=True)
        ws.cell(row=row, column=2, value=f"=SUM(B2:B{row-1})").font = Font(bold=True)
        ws.cell(row=row, column=4, value=f"=SUM(D2:D{row-1})").font = Font(bold=True)
        ws.cell(row=row, column=5, value=f"=SUM(E2:E{row-1})").font = Font(bold=True)

    # --- ЛИСТ 2: ПОКУПКИ ---
    ws2 = wb.create_sheet("Покупки")
    headers2 = ["Фактура доставчик", "Доставчик", "Данъчна основа",
                "ДДС 9%", "Общо платена сума"]
    ws2.append(headers2)
    for cell in ws2[1]:
        cell.font = Font(bold=True)

    purchases = get_purchases_journal(date_from, date_to)
    row = 2
    for p in purchases:
        total = p["Общо платена сума"]
        ws2.cell(row=row, column=1, value=p["Фактура доставчик"])
        ws2.cell(row=row, column=2, value=p["Доставчик"])
        ws2.cell(row=row, column=3, value=f"=E{row}/1.09")
        ws2.cell(row=row, column=4, value=f"=E{row}-C{row}")
        ws2.cell(row=row, column=5, value=total)
        row += 1

    if row > 2:
        ws2.cell(row=row, column=1, value="ОБЩО").font = Font(bold=True)
        ws2.cell(row=row, column=3, value=f"=SUM(C2:C{row-1})").font = Font(bold=True)
        ws2.cell(row=row, column=4, value=f"=SUM(D2:D{row-1})").font = Font(bold=True)
        ws2.cell(row=row, column=5, value=f"=SUM(E2:E{row-1})").font = Font(bold=True)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()    


def build_accounting_excel(date_from, date_to):
    """
    Връща Excel файл (в паметта, като bytes) с два листа:
    'Продажби' и 'Покупки'. Сумите с ДДС са стойности; основата и ДДС
    са Excel ФОРМУЛИ, за да е документът проверим и преизчислим.
    Връща bytes, готови за st.download_button.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from io import BytesIO

    wb = Workbook()

    # --- ЛИСТ 1: ПРОДАЖБИ ---
    ws = wb.active
    ws.title = "Продажби"
    headers = ["Документ", "Данъчна основа", "ДДС ставка", "Начислено ДДС",
               "Обща стойност с ДДС", "Фискална група", "Тип плащане", "Статус"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    sales = get_sales_journal(date_from, date_to)
    row = 2
    for s in sales:
        total = s["Обща стойност с ДДС"]
        is_voucher = s["ДДС ставка"] == "0%"
        ws.cell(row=row, column=1, value=s["Документ"])
        if is_voucher:
            ws.cell(row=row, column=2, value=total)
            ws.cell(row=row, column=3, value="0%")
            ws.cell(row=row, column=4, value=0)
        else:
            ws.cell(row=row, column=2, value=f"=E{row}/1.09")
            ws.cell(row=row, column=3, value=s["ДДС ставка"])
            ws.cell(row=row, column=4, value=f"=E{row}-B{row}")
        ws.cell(row=row, column=5, value=total)
        ws.cell(row=row, column=6, value=s["Фискална група"])
        ws.cell(row=row, column=7, value=s["Тип плащане"])
        ws.cell(row=row, column=8, value=s["Статус"])
        row += 1

    if row > 2:
        ws.cell(row=row, column=1, value="ОБЩО").font = Font(bold=True)
        ws.cell(row=row, column=2, value=f"=SUM(B2:B{row-1})").font = Font(bold=True)
        ws.cell(row=row, column=4, value=f"=SUM(D2:D{row-1})").font = Font(bold=True)
        ws.cell(row=row, column=5, value=f"=SUM(E2:E{row-1})").font = Font(bold=True)

    # --- ЛИСТ 2: ПОКУПКИ ---
    ws2 = wb.create_sheet("Покупки")
    headers2 = ["Фактура доставчик", "Доставчик", "Данъчна основа",
                "ДДС 9%", "Общо платена сума"]
    ws2.append(headers2)
    for cell in ws2[1]:
        cell.font = Font(bold=True)

    purchases = get_purchases_journal(date_from, date_to)
    row = 2
    for p in purchases:
        total = p["Общо платена сума"]
        ws2.cell(row=row, column=1, value=p["Фактура доставчик"])
        ws2.cell(row=row, column=2, value=p["Доставчик"])
        ws2.cell(row=row, column=3, value=f"=E{row}/1.09")
        ws2.cell(row=row, column=4, value=f"=E{row}-C{row}")
        ws2.cell(row=row, column=5, value=total)
        row += 1

    if row > 2:
        ws2.cell(row=row, column=1, value="ОБЩО").font = Font(bold=True)
        ws2.cell(row=row, column=3, value=f"=SUM(C2:C{row-1})").font = Font(bold=True)
        ws2.cell(row=row, column=4, value=f"=SUM(D2:D{row-1})").font = Font(bold=True)
        ws2.cell(row=row, column=5, value=f"=SUM(E2:E{row-1})").font = Font(bold=True)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()



# ---------- МЕСЕЧЕН ОТЧЕТ ЗА СТАТУС НА ПЛАЩАНИЯТА ----------

def get_monthly_payment_report(year_month):
    """
    Връща месечен отчет за плащанията. year_month е низ 'YYYY-MM'.
    Дели поръчките на неплатени (чакащи) и платени, за месеца по дата на създаване.
    Връща речник с трите суми и двата списъка.
    """
    conn = get_connection()

    # Неплатени (чакащи плащане) за месеца
    unpaid = conn.execute(
        """SELECT s.created_at, s.order_number, s.waybill_number,
                  s.payment_method,
                  s.supplementary_payment_method,
                  s.supplementary_amount,
                  COALESCE(SUM(si.quantity * si.sale_price), 0) AS amount
           FROM sales s
           LEFT JOIN sale_items si ON si.sale_id = s.id
           WHERE s.status = 'Чака плащане'
             AND strftime('%Y-%m', s.created_at) = ?
           GROUP BY s.id
           ORDER BY s.created_at""",
        (year_month,)
    ).fetchall()

    # Платени за месеца (с дата на плащане)
    paid = conn.execute(
        """SELECT s.created_at, s.order_number, s.waybill_number,
                  s.payment_method, 
                  s.supplementary_payment_method,
                  s.supplementary_amount,
                  s.payment_date,
                  COALESCE(SUM(si.quantity * si.sale_price), 0) AS amount
           FROM sales s
           LEFT JOIN sale_items si ON si.sale_id = s.id
           WHERE s.status = 'Платена'
             AND strftime('%Y-%m', s.created_at) = ?
           GROUP BY s.id
           ORDER BY s.created_at""",
        (year_month,)
    ).fetchall()

    unpaid_total = sum(r["amount"] for r in unpaid)
    paid_total = sum(r["amount"] for r in paid)

    def describe(r):
        d = dict(r)
        if d["payment_method"] == "Ваучер" and d["supplementary_amount"] > 0:
            d["payment_method"] = (f"Ваучер + {d['supplementary_payment_method']} "
                                   f"({d['supplementary_amount']:.2f} лв.)")
        return d

    return {
        "unpaid": [describe(r) for r in unpaid],
        "paid": [describe(r) for r in paid],
        "unpaid_total": unpaid_total,
        "paid_total": paid_total,
        "turnover": unpaid_total + paid_total,
    }

