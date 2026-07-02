import sqlite3

# Добавя invoice_file_path към deliveries за СЪЩЕСТВУВАЩА база.
# Безопасно за повторно пускане.

conn = sqlite3.connect("bookspace.db")
cols = [row[1] for row in conn.execute("PRAGMA table_info(deliveries)").fetchall()]

if "invoice_file_path" not in cols:
    conn.execute("ALTER TABLE deliveries ADD COLUMN invoice_file_path TEXT")
    conn.commit()
    print("Колоната invoice_file_path е добавена.")
else:
    print("Колоната invoice_file_path вече съществува — нищо не е променено.")

conn.close()
