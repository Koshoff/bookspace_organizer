import sqlite3

conn = sqlite3.connect("bookspace.db")

# Проверка дали таблицата вече съществува — за безопасност при повторно пускане.
exists = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='operating_expenses'"
).fetchone()

if exists:
    print("Таблица operating_expenses вече съществува — нищо не правя.")
else:
    conn.execute("""
        CREATE TABLE operating_expenses (
            id              INTEGER PRIMARY KEY,
            date            TEXT    NOT NULL,
            category        TEXT    NOT NULL,
            description     TEXT,
            amount          REAL    NOT NULL,
            document_number TEXT,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.commit()
    print("Таблица operating_expenses е създадена.")

conn.close()