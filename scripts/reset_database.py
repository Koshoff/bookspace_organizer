import os
import shutil
import sqlite3
from datetime import datetime

DB = "bookspace.db"

if os.path.exists(DB):
    backup_name = f"{DB}.backup_{datetime.now():%Y%m%d_%H%M%S}"
    shutil.copy(DB, backup_name)
    print(f"Резервно копие: {backup_name}")
    os.remove(DB)
    print(f"Изтрита {DB}")

conn = sqlite3.connect(DB)
# ВАЖНО: изключваме FK проверките за времето на пресъздаване,
# защото таблиците сочат една към друга и редът има значение.
conn.execute("PRAGMA foreign_keys = OFF")

with open("schema.sql", "r", encoding="utf-8") as f:
    conn.executescript(f.read())

conn.execute("PRAGMA foreign_keys = ON")
conn.commit()
conn.close()
print("Нова празна база е създадена с актуалната схема.")