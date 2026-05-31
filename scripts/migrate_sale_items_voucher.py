import sqlite3

conn = sqlite3.connect("bookspace.db")

# Проверка дали миграцията вече е минала (идемпотентност).
# Гледаме дали в новата схема product_id вече е nullable.
info = conn.execute("PRAGMA table_info(sale_items)").fetchall()
# table_info връща (cid, name, type, notnull, dflt, pk).
product_col = next((c for c in info if c[1] == "product_id"), None)

if product_col is None:
    raise SystemExit("Странно — няма product_id в sale_items. Спирам.")

if product_col[3] == 0:   # notnull == 0 значи "позволява NULL"
    print("Миграцията вече е минала — product_id е nullable. Нищо не правя.")
else:
    print("Започвам пренареждане на sale_items...")

    # Изключваме foreign keys временно за безопасно пренареждане.
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("BEGIN TRANSACTION")

    # 1) Нова таблица с правилната схема.
    conn.execute("""
        CREATE TABLE sale_items_new (
            id           INTEGER PRIMARY KEY,
            sale_id      INTEGER NOT NULL,
            product_id   INTEGER,     -- вече nullable: NULL при ваучер
            voucher_id   INTEGER,     -- nullable: NULL при книга
            quantity     INTEGER NOT NULL,
            cost_price   REAL    NOT NULL DEFAULT 0,
            sale_price   REAL    NOT NULL DEFAULT 0,
            -- Точно едно от двете трябва да е попълнено.
            CHECK ((product_id IS NULL) != (voucher_id IS NULL)),
            FOREIGN KEY (sale_id)    REFERENCES sales(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (voucher_id) REFERENCES vouchers(id)
        )
    """)

    # 2) Копираме съществуващите редове (всички са книги — voucher_id остава NULL).
    conn.execute("""
        INSERT INTO sale_items_new (id, sale_id, product_id, voucher_id,
                                    quantity, cost_price, sale_price)
        SELECT id, sale_id, product_id, NULL, quantity, cost_price, sale_price
        FROM sale_items
    """)

    # 3) Сваляме старата, преименуваме новата.
    conn.execute("DROP TABLE sale_items")
    conn.execute("ALTER TABLE sale_items_new RENAME TO sale_items")

    conn.execute("COMMIT")
    conn.execute("PRAGMA foreign_keys = ON")
    print("Готово. sale_items е пренаредена с nullable product_id + CHECK ограничение.")

conn.close()