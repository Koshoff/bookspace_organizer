from db.connection import get_connection
# само АКО функцията хваща sqlite3.IntegrityError:
import sqlite3

# ---------- СКЛАД И ОДИТ (Модул 7) ----------

def search_stock(search_term=None):
    """
    Връща книгите с текущата им наличност, опционално филтрирани по търсене
    в заглавие/автор/ISBN. Това е бързият преглед на склада.
    """
    conn = get_connection()
    query = """
        SELECT
            p.id,
            p.isbn,
            p.title,
            p.author,
            s.name AS supplier_name,
            p.cover_price,
            COALESCE((SELECT SUM(quantity_change) FROM stock_movements m
                      WHERE m.product_id = p.id), 0) AS stock
        FROM products p
        JOIN suppliers s ON s.id = p.supplier_id
    """
    params = []
    if search_term:
        # LIKE с % от двете страни = "съдържа някъде". Търсим в три полета.
        # Параметризирано — стойността влиза през ?, не се лепи в текста.
        query += """ WHERE p.title LIKE ? OR p.author LIKE ? OR p.isbn LIKE ?"""
        like = f"%{search_term}%"
        params = [like, like, like]
    query += " ORDER BY p.title"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def get_product_history(product_id):
    """
    Връща пълната хронология на движенията на една книга, най-новите отгоре.
    Това Е одитът: всеки ред е едно събитие с документ и оператор.
    """
    conn = get_connection()
    rows = conn.execute(
        """SELECT
               created_at,
               movement_type,
               quantity_change,
               document_ref,
               operator
           FROM stock_movements
           WHERE product_id = ?
           ORDER BY created_at DESC, id DESC""",
        (product_id,)
    ).fetchall()
    conn.close()
    return rows
