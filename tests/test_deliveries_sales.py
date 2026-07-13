"""Тестове за доставки, продажби, ваучери, сторно и складови справки."""
import pytest


# ---------- ДОСТАВКИ ----------

def test_delivery_adds_stock_and_snapshots_price(seed):
    db = seed.db
    sid = seed.supplier()
    pid = seed.product("978-1", "Книга", sid)
    b = db.get_product_for_delivery("978-1")
    assert b["last_delivery_price"] is None            # още няма история
    seed.deliver(sid, pid, 5, 12.5, percent=35.0)
    assert db.get_current_stock(pid) == 5
    b2 = db.get_product_for_delivery("978-1")
    assert b2["last_delivery_price"] == 12.5 and b2["last_discount_pct"] == 35.0


def test_get_deliveries_filters_and_total(seed):
    db = seed.db
    sid = seed.supplier()
    pid = seed.product("978-1", "Книга", sid)
    seed.deliver(sid, pid, 4, 10.0, doc="A", payment="По банка")
    seed.deliver(sid, pid, 2, 5.0, doc="B", payment="В брой")
    all_d = db.get_deliveries()
    assert len(all_d) == 2
    bank = db.get_deliveries(payment_type="По банка")
    assert len(bank) == 1 and bank[0]["total_amount"] == 40.0


# ---------- ПРОДАЖБИ ----------

def test_create_sale_reduces_stock(seed):
    db = seed.db
    sid = seed.supplier()
    pid = seed.product("978-1", "Книга", sid)
    seed.deliver(sid, pid, 10, 12.0)
    ok, _ = db.create_sale("ORD1", "w", [{"product_id": pid, "title": "Книга",
                                          "quantity": 4, "cost_price": 12.0,
                                          "sale_price": 20.0}], "В брой (Каса)")
    assert ok and db.get_current_stock(pid) == 6


def test_create_sale_insufficient_stock_rolls_back(seed):
    db = seed.db
    sid = seed.supplier()
    pid = seed.product("978-1", "Книга", sid)
    seed.deliver(sid, pid, 2, 12.0)
    ok, msg = db.create_sale("ORD1", "w", [{"product_id": pid, "title": "Книга",
                                            "quantity": 5, "cost_price": 12.0,
                                            "sale_price": 20.0}], "В брой (Каса)")
    assert not ok and "наличност" in msg
    assert db.get_current_stock(pid) == 2             # нищо не е продадено


def test_get_sales_by_waybills(seed):
    db = seed.db
    sid = seed.supplier()
    pid = seed.product("978-1", "Книга", sid)
    seed.deliver(sid, pid, 10, 12.0)
    db.create_sale("ORD9", "WB-777", [{"product_id": pid, "title": "Книга",
                                       "quantity": 1, "cost_price": 12.0,
                                       "sale_price": 25.90}], "Пощенски паричен превод (Куриер)")
    res = db.get_sales_by_waybills(["WB-777", "WB-000"])
    assert "WB-777" in res and abs(res["WB-777"]["total"] - 25.90) < 0.01
    assert "WB-000" not in res


def test_daily_supplier_reorders_excludes_cancelled(seed, run_sql):
    db = seed.db
    sid = seed.supplier()
    pid = seed.product("978-1", "Книга", sid)
    seed.deliver(sid, pid, 10, 12.0)
    db.create_sale("O1", "w", [{"product_id": pid, "title": "Книга", "quantity": 2,
                                "cost_price": 12.0, "sale_price": 20.0}], "В брой (Каса)")
    # отказана продажба не влиза в заявката
    db.create_sale("O2", "w", [{"product_id": pid, "title": "Книга", "quantity": 3,
                                "cost_price": 12.0, "sale_price": 20.0}], "В брой (Каса)")
    sid2 = [s for s in db.get_sales() if s["order_number"] == "O2"][0]["id"]
    db.cancel_sale(sid2, "BON1")
    run_sql("UPDATE sales SET created_at='2026-06-20 09:00:00' WHERE order_number IN ('O1','O2')")
    rows = db.get_daily_supplier_reorders("2026-06-20")
    assert len(rows) == 1 and rows[0]["total_sold"] == 2


# ---------- ВАУЧЕРИ ----------

def test_issue_and_validate_voucher(seed):
    db = seed.db
    ok, result = db.issue_voucher(50.0, "В брой (Каса)")
    assert ok and result["nominal"] == 50.0
    code = result["code"]
    ok2, v = db.validate_voucher_for_use(code)
    assert ok2 and v["status"] == "Активен"


def test_voucher_sale_marks_used(seed):
    db = seed.db
    sid = seed.supplier()
    pid = seed.product("978-1", "Книга", sid, cover=30.0)
    seed.deliver(sid, pid, 5, 12.0)
    ok, result = db.issue_voucher(50.0, "В брой (Каса)")
    voucher = db.find_voucher_by_code(result["code"])
    ok2, _ = db.create_sale_with_voucher(
        "ORD1", "w", [{"product_id": pid, "title": "Книга", "quantity": 1,
                       "cost_price": 12.0, "sale_price": 30.0}], voucher["id"])
    assert ok2
    assert db.find_voucher_by_code(result["code"])["status"] == "Използван"


def test_voucher_supplement_required_when_over_nominal(seed):
    db = seed.db
    sid = seed.supplier()
    pid = seed.product("978-1", "Книга", sid, cover=80.0)
    seed.deliver(sid, pid, 5, 12.0)
    result = db.issue_voucher(50.0, "В брой (Каса)")[1]
    voucher = db.find_voucher_by_code(result["code"])
    # 80 > 50 и няма метод на доплащане → отказ
    ok, msg = db.create_sale_with_voucher(
        "ORD1", "w", [{"product_id": pid, "title": "Книга", "quantity": 1,
                       "cost_price": 12.0, "sale_price": 80.0}], voucher["id"])
    assert not ok and "доплащане" in msg


def test_cancel_sale_returns_stock_and_records_credit_note(seed):
    db = seed.db
    sid = seed.supplier()
    pid = seed.product("978-1", "Книга", sid)
    seed.deliver(sid, pid, 10, 12.0)
    db.create_sale("O1", "w", [{"product_id": pid, "title": "Книга", "quantity": 3,
                                "cost_price": 12.0, "sale_price": 20.0}], "В брой (Каса)")
    sale_id = [s for s in db.get_sales() if s["order_number"] == "O1"][0]["id"]
    assert db.get_current_stock(pid) == 7
    ok, _ = db.cancel_sale(sale_id, "BON555")
    assert ok and db.get_current_stock(pid) == 10       # върнато на склад
    notes = db.get_credit_notes()
    assert len(notes) == 1 and notes[0]["returned_amount"] == 60.0


def test_cancel_voucher_sale_refused(seed):
    db = seed.db
    result = db.issue_voucher(50.0, "В брой (Каса)")[1]
    # продажбата при издаване на ваучер съдържа ваучерен ред → не се сторнира
    sale_id = result["sale_id"]
    ok, msg = db.cancel_sale(sale_id, "BON1")
    assert not ok and "ваучер" in msg.lower()


# ---------- СКЛАД ТЪРСЕНЕ ----------

def test_search_stock_by_author_publisher_isbn_and_available(seed):
    db = seed.db
    s1 = seed.supplier("Жанет 45")
    s2 = seed.supplier("Колибри")
    p1 = seed.product("111", "Физика на тъгата", s1, author="Георги Господинов")
    seed.product("222", "Времеубежище", s1, author="Георги Господинов")
    seed.product("333", "Друга", s2, author="Друг")
    seed.deliver(s1, p1, 5, 12.0)                     # само 111 има наличност
    assert len(db.search_stock("Господинов")) == 2    # по автор
    assert len(db.search_stock("Колибри")) == 1       # по издателство
    assert len(db.search_stock("222")) == 1           # по ISBN
    avail = db.search_stock("Господинов", available_only=True)
    assert len(avail) == 1 and avail[0]["isbn"] == "111"
    assert avail[0]["last_delivery_price"] == 12.0
