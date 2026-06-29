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



def get_all_products_full():
    """Връща ВСИЧКИ колони на артикулите (за пре-попълване при редакция),
    подредени по заглавие. За справки ползвай get_all_products (с наличност)."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM products ORDER BY title").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_product(product_id, isbn, title, author, supplier_id, cover_price,
                   vat_rate, year, cover_type, genre, description,
                   product_type="Книга", fiscal_group="Б"):
    """Обновява съществуващ артикул. Връща (True, съобщение) или (False, грешка).
    Хваща нарушение на UNIQUE(isbn) — друг артикул вече носи това ISBN."""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE products
               SET isbn = ?, title = ?, author = ?, supplier_id = ?,
                   cover_price = ?, vat_rate = ?, year = ?, cover_type = ?,
                   genre = ?, description = ?, product_type = ?, fiscal_group = ?
               WHERE id = ?""",
            (isbn, title, author, supplier_id, cover_price, vat_rate, year,
             cover_type, genre, description, product_type, fiscal_group,
             product_id)
        )
        conn.commit()
        return True, "Артикулът е обновен успешно."
    except sqlite3.IntegrityError:
        return False, f"Вече съществува друг артикул с ISBN „{isbn}“."
    finally:
        conn.close()


def delete_product(product_id):
    """Изтрива артикул САМО ако няма никаква история по него
    (доставки, продажби, складови движения). Артикул с история носи
    счетоводни следи — изтриването му би изкривило отчетите, затова го
    отказваме. Връща (True, съобщение) или (False, грешка)."""
    conn = get_connection()
    try:
        refs = conn.execute(
            """SELECT
                   (SELECT COUNT(*) FROM delivery_items WHERE product_id = ?) +
                   (SELECT COUNT(*) FROM sale_items     WHERE product_id = ?) +
                   (SELECT COUNT(*) FROM stock_movements WHERE product_id = ?)
                   AS c""",
            (product_id, product_id, product_id)
        ).fetchone()["c"]
        if refs > 0:
            return False, ("Не може да се изтрие — артикулът има история "
                           "(доставки/продажби/движения). Записите трябва да "
                           "се запазят за одита.")
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        return True, "Артикулът е изтрит."
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

