from db.connection import get_connection
# само АКО функцията хваща sqlite3.IntegrityError:
import sqlite3

# ---------- СКЛАД И ОДИТ (Модул 7) ----------

def search_stock(search_term=None, available_only=False):
    """
    Смарт търсене в склада: едно поле търси едновременно в заглавие, автор,
    ISBN и издателство (доставчик) чрез LIKE %query%. Връща и коричната и
    последната доставна цена.
    available_only=True скрива продуктите с наличност 0 (само това на рафта).
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
            p.last_delivery_price,
            COALESCE((SELECT SUM(quantity_change) FROM stock_movements m
                      WHERE m.product_id = p.id), 0) AS stock
        FROM products p
        JOIN suppliers s ON s.id = p.supplier_id
    """
    params = []
    if search_term:
        # LIKE с % от двете страни = "съдържа някъде". Едно поле → четири колони.
        # Параметризирано — стойността влиза през ?, не се лепи в текста.
        query += (" WHERE (p.title LIKE ? OR p.author LIKE ? "
                  "OR p.isbn LIKE ? OR s.name LIKE ?)")
        like = f"%{search_term}%"
        params = [like, like, like, like]
    query += " ORDER BY p.title"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    if available_only:
        # Наличността е изведена (сбор от движенията) → филтрираме в Python.
        result = [r for r in result if r["stock"] > 0]
    return result


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
