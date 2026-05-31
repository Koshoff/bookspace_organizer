import sqlite3

conn = sqlite3.connect("bookspace.db")
cols = [r[1] for r in conn.execute("PRAGMA table_info(sales)").fetchall()]

if "supplementary_payment_method" not in cols:
    conn.execute(
        """ALTER TABLE sales
           ADD COLUMN supplementary_payment_method TEXT"""
    )
    print("Добавена supplementary_payment_method.")
else:
    print("supplementary_payment_method вече съществува.")

if "supplementary_amount" not in cols:
    conn.execute(
        """ALTER TABLE sales
           ADD COLUMN supplementary_amount REAL NOT NULL DEFAULT 0"""
    )
    print("Добавена supplementary_amount.")
else:
    print("supplementary_amount вече съществува.")

conn.commit()
conn.close()