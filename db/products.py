from db.connection import get_connection
# само АКО функцията хваща sqlite3.IntegrityError:
import sqlite3

# ---------- ПРОДУКТИ / КАТАЛОГ (Модул 2) ----------

def get_all_products():
    """Връща всички книги ЗАЕДНО с името на доставчика и текущата наличност.
    Това е първата ни заявка с JOIN — обединява две таблици в един резултат."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT
               p.id,
               p.isbn,
               p.title,
               p.author,
               s.name AS supplier_name,        -- името идва от suppliers чрез JOIN
               p.cover_price,
               p.vat_rate,
               p.genre,
               -- Наличността = сборът на движенията. COALESCE прави NULL->0,
               -- защото книга без никакви движения няма редове в stock_movements.
               COALESCE((SELECT SUM(quantity_change)
                         FROM stock_movements m
                         WHERE m.product_id = p.id), 0) AS stock
           FROM products p
           JOIN suppliers s ON s.id = p.supplier_id   -- свързваме по релацията
           ORDER BY p.title"""
    ).fetchall()
    conn.close()
    return rows


def add_product(isbn, title, author, supplier_id, cover_price, vat_rate,
                year, cover_type, genre, description,
                product_type="Книга", fiscal_group="Б"):
    """Добавя нов артикул (книга или ваучер).
    product_type: 'Книга' или 'Ваучер'.
    fiscal_group: 'Б' (9% ДДС) или 'Д' (0% ДДС, ваучери).
    """
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO products
               (isbn, title, author, supplier_id, cover_price, vat_rate,
                year, cover_type, genre, description, product_type, fiscal_group)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (isbn, title, author, supplier_id, cover_price, vat_rate,
             year, cover_type, genre, description, product_type, fiscal_group)
        )
        conn.commit()
        return True, f"{product_type}-ът е добавен успешно."
    except sqlite3.IntegrityError:
        return False, f"Вече съществува артикул с ISBN „{isbn}“."
    finally:
        conn.close()



def get_products_for_delivery():
    """Връща книгите във вид, удобен за избор при доставка:
    {ISBN: {id, title, author, supplier_id}}. Ползва се за сканиране по ISBN."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, isbn, title, author, supplier_id FROM products"
    ).fetchall()
    conn.close()
    return {r["isbn"]: dict(r) for r in rows}

