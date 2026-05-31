"""
Реалистични тестови данни за Bookspace.
Пуска се ВЕДНЪЖ върху празна база (след reset_database.py).
Генерира данни за около 17 месеца назад, за да може да се тества:
- Обезценка (книги без продажби 12+ месеца).
- Сравнения между периоди в таблото.
- Инвентаризация към минала дата.
- Целият счетоводен експорт.
"""
import sqlite3
from datetime import datetime, timedelta
import random

random.seed(42)   # Същите "случайни" данни при всяко пускане. Полезно за тест.

conn = sqlite3.connect("bookspace.db")
cur = conn.cursor()

today = datetime.now()

# =============== 1. ДОСТАВЧИЦИ ===============
suppliers = [
    ("Сиела", "131282355", "Иван Петров", "София, бул. Витоша 100",
     "02/9876543", "office@ciela.bg", 35.0),
    ("Колибри", "131456789", "Мария Иванова", "София, ул. Цар Самуил 25",
     "02/9123456", "books@colibri.bg", 40.0),
    ("Изток-Запад", "131789012", "Петър Стоянов", "София, ул. Граф Игнатиев 12",
     "02/9555444", "info@iztok-zapad.eu", 38.0),
    ("Хермес", "131345678", "Анна Георгиева", "Пловдив, бул. Цар Борис III 50",
     "032/123456", "office@hermesbooks.com", 35.0),
    ("Лист", "131234567", "Стоян Димитров", "София, ул. Иван Вазов 7",
     "02/8765432", "contact@listbooks.bg", 42.0),
]
for s in suppliers:
    cur.execute(
        """INSERT INTO suppliers (name, bulstat, mol, address, phone, email,
                                  default_discount)
           VALUES (?, ?, ?, ?, ?, ?, ?)""", s
    )
supplier_ids = list(range(1, len(suppliers) + 1))
print(f"✓ {len(suppliers)} доставчика")

# =============== 2. КНИГИ ===============
books = [
    # (isbn, заглавие, автор, supplier_id, корична цена, жанр, година)
    ("9789542819394", "Под игото", "Иван Вазов", 1, 18.90, "Българска класика", 2023),
    ("9789542819400", "Бай Ганьо", "Алеко Константинов", 1, 14.50, "Българска класика", 2023),
    ("9789545297854", "Време разделно", "Антон Дончев", 1, 22.00, "Историческа", 2022),
    ("9789547834521", "Тютюн", "Димитър Димов", 2, 26.50, "Българска класика", 2023),
    ("9789549231456", "Хайка за вълци", "Ивайло Петров", 2, 19.90, "Българска класика", 2022),
    ("9786190101234", "Майстора и Маргарита", "Михаил Булгаков", 3, 28.90, "Руска класика", 2024),
    ("9786190102345", "Престъпление и наказание", "Достоевски", 3, 24.50, "Руска класика", 2023),
    ("9786190103456", "Анна Каренина", "Л. Н. Толстой", 3, 32.00, "Руска класика", 2024),
    ("9789542819999", "1984", "Джордж Оруел", 4, 16.90, "Дистопия", 2024),
    ("9789542820001", "Скотовъдна ферма", "Джордж Оруел", 4, 13.50, "Дистопия", 2023),
    ("9789542820002", "Дюна", "Франк Хърбърт", 4, 35.00, "Фантастика", 2024),
    ("9786197578012", "Сапиенс", "Ювал Ноа Харари", 5, 29.90, "История", 2024),
    ("9786197578023", "Хомо Деус", "Ювал Ноа Харари", 5, 28.50, "Футурология", 2024),
    ("9786197578034", "Мисли бързо и бавно", "Даниел Канеман", 5, 31.00, "Психология", 2023),
    ("9789542830001", "Малкият принц", "Сент-Екзюпери", 1, 12.90, "Детска", 2023),
    ("9789542830002", "Хари Потър 1", "Дж. К. Роулинг", 2, 22.90, "Детска", 2024),
    ("9789542830003", "Властелинът на пръстените", "Дж. Р. Р. Толкин", 4, 45.00, "Фентъзи", 2024),
    # Тези две са нарочно от много отдавна — за тест на обезценката.
    ("9789999990001", "Старо забравено заглавие", "Неизвестен автор", 3, 15.00, "Друго", 2019),
    ("9789999990002", "Прашна тухла", "Друг неизвестен", 5, 18.00, "Друго", 2018),
    # Една нова, която няма да продаваме (за тест "наскоро добавена, нула продажби").
    ("9789999990003", "Нова книга 2026", "Нов автор", 1, 20.00, "Нова", 2026),
]
for b in books:
    isbn, title, author, sup_id, price, genre, year = b
    cur.execute(
        """INSERT INTO products (isbn, title, author, supplier_id, cover_price,
                                 vat_rate, year, genre, cover_type, product_type, fiscal_group)
           VALUES (?, ?, ?, ?, ?, 9, ?, ?, 'Мека', 'Книга', 'Б')""",
        (isbn, title, author, sup_id, price, year, genre)
    )
product_ids = list(range(1, len(books) + 1))
print(f"✓ {len(books)} книги")

# =============== 3. ДОСТАВКИ ===============
# Разпределени през 17 месеца. Стари за тест на обезценка, скорошни за актуални отчети.
# Доставната цена ≈ 50-60% от коричната (типична отстъпка за книжарници).

def days_ago(n):
    return (today - timedelta(days=n)).strftime("%Y-%m-%d")

# (дни назад, supplier_id, doc_type, doc_number, payment_type, payment_status, paid_date_offset)
delivery_specs = [
    # Стари доставки (за обезценка) — над 12 месеца
    (450, 3, "Фактура", "F-2024-101", "По банка", "Платена", 440),
    (430, 5, "Фактура", "F-2024-205", "По банка", "Платена", 420),
    (400, 1, "Фактура", "F-2024-301", "По банка", "Платена", 390),
    # Средно стари — около 6-9 месеца
    (250, 2, "Фактура", "F-2025-150", "По банка", "Платена", 240),
    (200, 4, "Стокова разписка", "SR-2025-77", "В брой", "Платена", 200),
    (180, 1, "Протокол консигнация", "K-2025-12", "Консигнация (отложено)", "Неплатена", None),
    # Скорошни
    (90, 3, "Фактура", "F-2026-50", "По банка", "Платена", 80),
    (60, 5, "Фактура", "F-2026-120", "По банка", "Неплатена", None),
    (30, 2, "Протокол консигнация", "K-2026-8", "Консигнация (отложено)", "Неплатена", None),
    (10, 4, "Фактура", "F-2026-200", "По банка", "Платена", 5),
]

# Помощник: задава кои книги влизат в коя доставка.
# Грубо разделяме книгите по доставчик.
books_by_supplier = {}
for i, b in enumerate(books, start=1):
    sup = b[3]
    books_by_supplier.setdefault(sup, []).append(i)

# Какъв е settlement_type: при тип на доставката "Консигнация (отложено)" → "Консигнация"
def settlement_for(payment_type):
    return "Консигнация" if "Консигнация" in payment_type else "Купена"

for spec in delivery_specs:
    days, sup_id, doc_type, doc_num, pay_type, pay_status, paid_offset = spec
    doc_date = days_ago(days)
    paid_date = days_ago(paid_offset) + " 10:00:00" if paid_offset else None

    cur.execute(
        """INSERT INTO deliveries (supplier_id, doc_type, doc_number, doc_date,
                                   payment_status, delivery_paid_date, payment_type, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (sup_id, doc_type, doc_num, doc_date, pay_status, paid_date, pay_type,
         doc_date + " 09:00:00")
    )
    delivery_id = cur.lastrowid

    # Добавяме 2-4 книги от този доставчик в доставката, с по 3-10 бройки.
    sup_books = books_by_supplier.get(sup_id, [])
    chosen = random.sample(sup_books, min(len(sup_books), random.randint(2, 4)))
    settlement = settlement_for(pay_type)

    for pid in chosen:
        qty = random.randint(3, 10)
        # Доставна цена ≈ 55% от коричната (cover_price = books[pid-1][4])
        cover = books[pid - 1][4]
        delivery_price = round(cover * 0.55, 2)
        cur.execute(
            """INSERT INTO delivery_items (delivery_id, product_id, quantity,
                                           settlement_type, supplier_percent, delivery_price)
               VALUES (?, ?, ?, ?, 35, ?)""",
            (delivery_id, pid, qty, settlement, delivery_price)
        )
        # Складово движение: +qty
        cur.execute(
            """INSERT INTO stock_movements (product_id, movement_type, quantity_change,
                                            document_ref, operator, created_at)
               VALUES (?, 'Доставка', ?, ?, 'seed', ?)""",
            (pid, qty, f"{doc_type} №{doc_num}", doc_date + " 09:30:00")
        )

print(f"✓ {len(delivery_specs)} доставки със складови движения")

# =============== 4. ПРОДАЖБИ ===============
# Разпределени продажби — част платени, част чакащи, една отказана.
# Избягваме старите книги (id 18, 19) → те ще останат залежали.
sellable = [p for p in product_ids if p not in (18, 19, 20)]

# (дни назад, статус, метод на плащане, брой различни заглавия)
sale_specs = [
    (200, "Платена", "В брой (Каса)", 2),
    (180, "Платена", "Банков път / Карта", 1),
    (150, "Платена", "Пощенски паричен превод (Куриер)", 3),
    (120, "Отказана", "Пощенски паричен превод (Куриер)", 2),  # ще има кредитно известие
    (90, "Платена", "В брой (Каса)", 2),
    (60, "Платена", "Банков път / Карта", 1),
    (45, "Платена", "Пощенски паричен превод (Куриер)", 2),
    (30, "Платена", "В брой (Каса)", 1),
    (20, "Чака плащане", "Пощенски паричен превод (Куриер)", 2),
    (10, "Чака плащане", "Пощенски паричен превод (Куриер)", 3),
    (5, "Платена", "Банков път / Карта", 1),
    (3, "Чака плащане", "Пощенски паричен превод (Куриер)", 2),
    (1, "Платена", "В брой (Каса)", 2),
]

sale_ids = []
order_counter = 1000

for spec in sale_specs:
    days, status, method, item_count = spec
    sale_date = days_ago(days) + f" {random.randint(9, 18):02d}:{random.randint(0, 59):02d}:00"
    order_num = f"ORD-{order_counter}"
    waybill = f"SP{random.randint(1000000, 9999999)}" if "Куриер" in method else ""
    paid_date = sale_date if status == "Платена" else None
    order_counter += 1

    cur.execute(
        """INSERT INTO sales (order_number, waybill_number, status, payment_date,
                              payment_method, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (order_num, waybill, status, paid_date, method, sale_date)
    )
    sale_id = cur.lastrowid
    sale_ids.append((sale_id, status, sale_date, order_num))

    # Добавяме редове
    chosen = random.sample(sellable, item_count)
    for pid in chosen:
        qty = random.randint(1, 3)
        cover = books[pid - 1][4]
        cost = round(cover * 0.55, 2)
        cur.execute(
            """INSERT INTO sale_items (sale_id, product_id, quantity, cost_price, sale_price)
               VALUES (?, ?, ?, ?, ?)""",
            (sale_id, pid, qty, cost, cover)
        )
        # Складово движение: -qty
        cur.execute(
            """INSERT INTO stock_movements (product_id, movement_type, quantity_change,
                                            document_ref, operator, created_at)
               VALUES (?, 'Продажба', ?, ?, 'seed', ?)""",
            (pid, -qty, f"Поръчка №{order_num}", sale_date)
        )

print(f"✓ {len(sale_specs)} продажби със складови движения")

# =============== 5. КРЕДИТНО ИЗВЕСТИЕ за отказаната продажба ===============
cancelled = [s for s in sale_ids if s[1] == "Отказана"][0]
cancel_sale_id, _, cancel_date, cancel_order = cancelled

# Връщаме редовете на склад
returned_items = cur.execute(
    "SELECT product_id, quantity, sale_price FROM sale_items WHERE sale_id = ?",
    (cancel_sale_id,)
).fetchall()
returned_amount = sum(q * p for _, q, p in returned_items)

# Сторното се случва ден след продажбата
return_date = (datetime.strptime(cancel_date, "%Y-%m-%d %H:%M:%S") + timedelta(days=1)
               ).strftime("%Y-%m-%d %H:%M:%S")

for pid, qty, _ in returned_items:
    cur.execute(
        """INSERT INTO stock_movements (product_id, movement_type, quantity_change,
                                        document_ref, operator, created_at)
           VALUES (?, 'Сторно', ?, ?, 'seed', ?)""",
        (pid, qty, f"Кредитно известие (бележка №CB-{cancel_order})", return_date)
    )

cur.execute(
    """INSERT INTO credit_notes (sale_id, original_receipt, returned_amount, created_at)
       VALUES (?, ?, ?, ?)""",
    (cancel_sale_id, f"CB-{cancel_order}", returned_amount, return_date)
)
print(f"✓ 1 кредитно известие (върнат склад)")

# =============== 6. ВАУЧЕРИ ===============
# Издаваме няколко ваучера — част активни, един използван.
voucher_specs = [
    (40, 50.0, "В брой (Каса)", False),
    (30, 30.0, "Банков път / Карта", True),    # ще е използван
    (15, 100.0, "В брой (Каса)", False),
    (5, 25.0, "В брой (Каса)", False),
]

year_now = today.year
for i, (days, nominal, method, will_use) in enumerate(voucher_specs, start=1):
    issue_date = days_ago(days) + " 12:00:00"
    valid_until = (today - timedelta(days=days) + timedelta(days=365)).strftime("%Y-%m-%d")
    code = f"GIFT-{year_now}-{i:05d}"

    # Продажба за издаване
    cur.execute(
        """INSERT INTO sales (order_number, status, payment_method, payment_date, created_at)
           VALUES (?, 'Платена', ?, ?, ?)""",
        (f"VOUCHER-{code}", method, issue_date, issue_date)
    )
    issue_sale_id = cur.lastrowid

    status = "Използван" if will_use else "Активен"
    cur.execute(
        """INSERT INTO vouchers (code, nominal, status, valid_until, issued_at, issued_sale_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (code, nominal, status, valid_until, issue_date, issue_sale_id)
    )
    voucher_id = cur.lastrowid

    # Ред в sale_items за издаването
    cur.execute(
        """INSERT INTO sale_items (sale_id, voucher_id, quantity, cost_price, sale_price)
           VALUES (?, ?, 1, 0, ?)""",
        (issue_sale_id, voucher_id, nominal)
    )

print(f"✓ {len(voucher_specs)} ваучера")

conn.commit()
conn.close()
print("\n🎉 Готово. Базата е напълнена с реалистични тестови данни.")