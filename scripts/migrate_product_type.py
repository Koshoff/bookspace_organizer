import sqlite3

conn = sqlite3.connect("bookspace.db")

cols = [row[1] for row in conn.execute("PRAGMA table_info(products)").fetchall()]

if "product_type" not in cols:
    conn.execute(
        """ALTER TABLE products
           ADD COLUMN product_type TEXT NOT NULL DEFAULT 'Книга'"""
    )
    print("Колоната product_type е добавена.")
else:
    print("product_type вече съществува.")

if "fiscal_group" not in cols:
    conn.execute(
        """ALTER TABLE products
           ADD COLUMN fiscal_group TEXT NOT NULL DEFAULT 'Б'"""
    )
    print("Колоната fiscal_group е добавена.")
else:
    print("fiscal_group вече съществува.")

conn.commit()
conn.close()