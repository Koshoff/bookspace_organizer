import sqlite3

# Добавя last_delivery_price и last_discount_pct към products за СЪЩЕСТВУВАЩА база.
# Безопасно за повторно пускане. NULL = още няма историческа доставна цена.

conn = sqlite3.connect("bookspace.db")
cols = [row[1] for row in conn.execute("PRAGMA table_info(products)").fetchall()]

added = []
if "last_delivery_price" not in cols:
    conn.execute("ALTER TABLE products ADD COLUMN last_delivery_price REAL")
    added.append("last_delivery_price")
if "last_discount_pct" not in cols:
    conn.execute("ALTER TABLE products ADD COLUMN last_discount_pct REAL")
    added.append("last_discount_pct")

conn.commit()
conn.close()

if added:
    print("Добавени колони:", ", ".join(added))
else:
    print("Колоните вече съществуват — нищо не е променено.")
