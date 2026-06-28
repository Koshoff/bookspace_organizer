import sqlite3

# Добавя индекси за производителност към СЪЩЕСТВУВАЩА база.
# Безопасно за повторно пускане — всички индекси са IF NOT EXISTS.
# Новите бази вече ги получават от schema.sql; този скрипт е за старите.

conn = sqlite3.connect("bookspace.db")

indexes = [
    # Най-важният: наличността = SUM(quantity_change) по product_id, смята се навсякъде.
    "CREATE INDEX IF NOT EXISTS idx_stock_movements_product   ON stock_movements(product_id)",
    "CREATE INDEX IF NOT EXISTS idx_sale_items_sale           ON sale_items(sale_id)",
    "CREATE INDEX IF NOT EXISTS idx_sale_items_product        ON sale_items(product_id)",
    "CREATE INDEX IF NOT EXISTS idx_delivery_items_delivery   ON delivery_items(delivery_id)",
    "CREATE INDEX IF NOT EXISTS idx_delivery_items_product    ON delivery_items(product_id)",
    "CREATE INDEX IF NOT EXISTS idx_sales_status              ON sales(status)",
    "CREATE INDEX IF NOT EXISTS idx_deliveries_payment_status ON deliveries(payment_status)",
]

for sql in indexes:
    conn.execute(sql)

conn.commit()
conn.close()

print(f"Готово: {len(indexes)} индекса са налични (създадени или вече съществуващи).")
