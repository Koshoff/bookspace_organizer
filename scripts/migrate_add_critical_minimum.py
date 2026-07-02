import sqlite3

# Добавя колоната critical_minimum към products за СЪЩЕСТВУВАЩА база.
# Безопасно за повторно пускане (проверява дали колоната вече я има).

conn = sqlite3.connect("bookspace.db")
cols = [row[1] for row in conn.execute("PRAGMA table_info(products)").fetchall()]

if "critical_minimum" not in cols:
    conn.execute(
        "ALTER TABLE products ADD COLUMN critical_minimum INTEGER NOT NULL DEFAULT 3"
    )
    conn.commit()
    print("Колоната critical_minimum е добавена (по подразбиране 3).")
else:
    print("Колоната critical_minimum вече съществува — нищо не е променено.")

conn.close()
