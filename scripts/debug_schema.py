import sqlite3
import re

with open("schema.sql", "r", encoding="utf-8") as f:
    content = f.read()

# Разделяме на отделни statement-и по ;
statements = [s.strip() for s in content.split(";") if s.strip()]

conn = sqlite3.connect(":memory:")
conn.execute("PRAGMA foreign_keys = OFF")

for i, stmt in enumerate(statements):
    try:
        conn.execute(stmt)
        # Извличаме името на таблицата от CREATE TABLE за читаемост.
        m = re.search(r"CREATE TABLE.*?(\w+)\s*\(", stmt, re.IGNORECASE | re.DOTALL)
        name = m.group(1) if m else "PRAGMA/друго"
        print(f"OK #{i}: {name}")
    except sqlite3.OperationalError as e:
        print(f"\nГРЕШКА на statement #{i}:")
        print(f"  {e}")
        print(f"\nСъдържание на statement-а:\n{stmt[:500]}")
        break