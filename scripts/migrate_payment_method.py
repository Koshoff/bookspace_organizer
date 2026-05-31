import sqlite3

conn = sqlite3.connect("bookspace.db")

# Проверяваме дали колоната вече съществува, за да е безопасно при повторно пускане.
cols = [row[1] for row in conn.execute("PRAGMA table_info(sales)").fetchall()]

if "payment_method" not in cols:
    # ALTER TABLE ADD COLUMN добавя колоната към съществуващата таблица.
    # DEFAULT гарантира, че СТАРИТЕ редове също получават стойност (не NULL).
    conn.execute(
        """ALTER TABLE sales
           ADD COLUMN payment_method TEXT NOT NULL
           DEFAULT 'Пощенски паричен превод'"""
    )
    conn.commit()
    print("Колоната payment_method е добавена успешно.")
else:
    print("Колоната payment_method вече съществува — нищо не е променено.")

conn.close()