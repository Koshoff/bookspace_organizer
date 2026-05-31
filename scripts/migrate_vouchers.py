import sqlite3

conn = sqlite3.connect("bookspace.db")

# 1) Създаваме таблицата vouchers (IF NOT EXISTS — безопасно при повторно пускане).
conn.execute("""
    CREATE TABLE IF NOT EXISTS vouchers (
        id              INTEGER PRIMARY KEY,
        code            TEXT    NOT NULL UNIQUE,
        nominal         REAL    NOT NULL,
        status          TEXT    NOT NULL DEFAULT 'Активен',
        valid_until     TEXT,
        issued_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
        used_at         TEXT,
        issued_sale_id  INTEGER,
        used_sale_id    INTEGER,
        FOREIGN KEY (issued_sale_id) REFERENCES sales(id),
        FOREIGN KEY (used_sale_id) REFERENCES sales(id)
    )
""")
print("Таблица vouchers — готова.")

# 2) Добавяме voucher_id към sale_items (за да може ред в продажба да е ваучер).
cols = [r[1] for r in conn.execute("PRAGMA table_info(sale_items)").fetchall()]
if "voucher_id" not in cols:
    # ПРАВИМ product_id ОПЦИОНАЛНО индиректно: понеже SQLite не позволява
    # лесно махане на NOT NULL, оставяме product_id както е, но ще го
    # запълваме само за книги. За ваучери ще пишем voucher_id, а product_id
    # ще оставим да сочи към специален "технически" продукт или 0.
    # По-чисто решение след малко (виж бележката).
    conn.execute("ALTER TABLE sale_items ADD COLUMN voucher_id INTEGER REFERENCES vouchers(id)")
    print("Колоната voucher_id е добавена към sale_items.")
else:
    print("voucher_id вече съществува в sale_items.")

# 3) Чистим евентуални ваучер-като-продукт записи, които си добавил по-рано.
removed = conn.execute(
    "DELETE FROM products WHERE product_type = 'Ваучер'"
).rowcount
if removed:
    print(f"Изтрити {removed} ваучер-като-продукт записа от products.")

conn.commit()
conn.close()
print("Готово.")