import sqlite3

conn = sqlite3.connect("bookspace.db")

cols = [row[1] for row in conn.execute("PRAGMA table_info(deliveries)").fetchall()]

if "payment_type" not in cols:
    conn.execute(
        """ALTER TABLE deliveries
           ADD COLUMN payment_type TEXT NOT NULL
           DEFAULT 'Консигнация (отложено)'"""
    )
    conn.commit()
    print("Колоната payment_type е добавена успешно.")
else:
    print("Колоната payment_type вече съществува — нищо не е променено.")

conn.close()