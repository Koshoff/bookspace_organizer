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
                product_type="Книга", fiscal_group="Б", critical_minimum=3):
    """Добавя нов артикул (книга или ваучер).
    product_type: 'Книга' или 'Ваучер'.
    fiscal_group: 'Б' (9% ДДС) или 'Д' (0% ДДС, ваучери).
    critical_minimum: праг на наличност, под който ПОС-ът алармира.
    """
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO products
               (isbn, title, author, supplier_id, cover_price, vat_rate,
                year, cover_type, genre, description, product_type, fiscal_group,
                critical_minimum)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (isbn, title, author, supplier_id, cover_price, vat_rate,
             year, cover_type, genre, description, product_type, fiscal_group,
             critical_minimum)
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
                   product_type="Книга", fiscal_group="Б", critical_minimum=3):
    """Обновява съществуващ артикул. Връща (True, съобщение) или (False, грешка).
    Хваща нарушение на UNIQUE(isbn) — друг артикул вече носи това ISBN."""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE products
               SET isbn = ?, title = ?, author = ?, supplier_id = ?,
                   cover_price = ?, vat_rate = ?, year = ?, cover_type = ?,
                   genre = ?, description = ?, product_type = ?, fiscal_group = ?,
                   critical_minimum = ?
               WHERE id = ?""",
            (isbn, title, author, supplier_id, cover_price, vat_rate, year,
             cover_type, genre, description, product_type, fiscal_group,
             critical_minimum, product_id)
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


def get_catalog_for_matching():
    """
    Връща ЦЕЛИЯ каталог от книги наведнъж — с доставчик, имейл, стандартна
    отстъпка, корична и последна доставна цена. Зарежда се ВЕДНЪЖ при импорт,
    за да става засичането (по ISBN и по заглавие) в паметта, без отделна
    заявка на ред (избягва N+1).
    """
    conn = get_connection()
    rows = conn.execute(
        """SELECT p.id, p.isbn, p.title, p.author, p.cover_price,
                  sup.id    AS supplier_id,
                  sup.name  AS supplier_name,
                  sup.email AS supplier_email,
                  sup.default_discount AS default_discount,
                  COALESCE((SELECT di.delivery_price FROM delivery_items di
                            WHERE di.product_id = p.id
                            ORDER BY di.id DESC LIMIT 1), 0) AS last_cost
           FROM products p
           JOIN suppliers sup ON sup.id = p.supplier_id
           WHERE p.product_type = 'Книга'"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_product_for_delivery(isbn):
    """
    Връща данните на книга по ISBN за екрана „Нова доставка": корична цена,
    ИСТОРИЧЕСКИ last_delivery_price / last_discount_pct (може да са NULL, ако
    още няма доставка) и стандартната отстъпка на доставчика (за първоначално
    попълване, когато няма история). Връща dict или None.
    """
    conn = get_connection()
    row = conn.execute(
        """SELECT p.id, p.isbn, p.title, p.cover_price,
                  p.last_delivery_price, p.last_discount_pct,
                  s.default_discount AS default_discount
           FROM products p
           JOIN suppliers s ON s.id = p.supplier_id
           WHERE p.isbn = ?""",
        (isbn.strip(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_product_delivery_history(product_id):
    """История на ДОСТАВКИТЕ (покупките) за една книга — за екрана „Досие".
    Всеки ред: дата, тип/номер документ, доставчик, количество, доставна цена."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT d.doc_date, d.doc_type, d.doc_number,
                  sup.name AS supplier_name,
                  di.quantity, di.delivery_price, di.settlement_type
           FROM delivery_items di
           JOIN deliveries d  ON d.id = di.delivery_id
           JOIN suppliers sup ON sup.id = d.supplier_id
           WHERE di.product_id = ?
           ORDER BY d.doc_date DESC, d.id DESC""",
        (product_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_product_sales_history(product_id):
    """История на ПРОДАЖБИТЕ за една книга (ПОС или импорт от сайта).
    Всеки ред: дата/час, номер поръчка, статус, продадено количество, цена."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT s.created_at, s.order_number, s.status,
                  si.quantity, si.sale_price
           FROM sale_items si
           JOIN sales s ON s.id = si.sale_id
           WHERE si.product_id = ?
           ORDER BY s.created_at DESC, s.id DESC""",
        (product_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_products_for_delivery():
    """Връща книгите във вид, удобен за избор при доставка:
    {ISBN: {id, title, author, supplier_id}}. Ползва се за сканиране по ISBN."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, isbn, title, author, supplier_id FROM products"
    ).fetchall()
    conn.close()
    return {r["isbn"]: dict(r) for r in rows}

