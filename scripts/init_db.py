import sqlite3

# Свързваме се към файла на базата. Ако bookspace.db не съществува — създава се.
conn = sqlite3.connect("bookspace.db")

# Прочитаме целия SQL от schema.sql и го изпълняваме наведнъж.
# executescript позволява много заявки в един низ (разделени с ;).
with open("schema.sql", "r", encoding="utf-8") as f:
    conn.executescript(f.read())

conn.commit()   # потвърждаваме промените (записваме ги трайно)
conn.close()

print("Базата е създадена успешно: bookspace.db")