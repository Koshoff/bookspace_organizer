import sqlite3

conn = sqlite3.connect("bookspace.db")

# Питаме вътрешната таблица sqlite_master — там SQLite пази какво съдържа базата.
tables = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()

print("Таблици в базата:")
for t in tables:
    print(f"  - {t[0]}")

conn.close()