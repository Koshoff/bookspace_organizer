"""Тестове за номенклатурата: доставчици и продукти (CRUD, guard-ове, досие)."""


# ---------- ДОСТАВЧИЦИ ----------

def test_add_supplier_and_duplicate(fresh_db):
    db = fresh_db
    ok, _ = db.add_supplier("Сиела", "1", "м", "а", "т", "e@x.bg", 35.0)
    assert ok
    ok2, msg = db.add_supplier("Сиела", "2", "м", "а", "т", "e2@x.bg", 40.0)
    assert not ok2 and "Сиела" in msg          # UNIQUE(name) нарушение


def test_update_supplier(seed):
    db = seed.db
    sid = seed.supplier("Сиела", 35.0)
    ok, _ = db.update_supplier(sid, "Сиела Нова", "9", "МОЛ2", "адр2",
                               "тел2", "нов@x.bg", 42.0)
    assert ok
    s = [x for x in db.get_all_suppliers() if x["id"] == sid][0]
    assert s["name"] == "Сиела Нова" and s["default_discount"] == 42.0


def test_update_supplier_duplicate_name(seed):
    db = seed.db
    seed.supplier("Сиела")
    sid2 = seed.supplier("Колибри")
    ok, msg = db.update_supplier(sid2, "Сиела", "", "", "", "", "e@x.bg", 30)
    assert not ok                                # друг вече носи „Сиела"


def test_delete_supplier_blocked_when_has_products(seed):
    db = seed.db
    sid = seed.supplier()
    seed.product("978-1", "Книга", sid)
    ok, msg = db.delete_supplier(sid)
    assert not ok and "книги" in msg


def test_delete_supplier_ok_when_empty(seed):
    db = seed.db
    sid = seed.supplier()
    ok, _ = db.delete_supplier(sid)
    assert ok and db.get_all_suppliers() == []


# ---------- ПРОДУКТИ ----------

def test_add_product_defaults_zero_stock_and_visible(seed):
    db = seed.db
    sid = seed.supplier()
    pid = seed.product("978-1", "Нова", sid)
    assert db.get_current_stock(pid) == 0                       # без движения → 0
    assert any(p["isbn"] == "978-1" for p in db.get_all_products())  # вижда се


def test_add_product_duplicate_isbn(seed):
    db = seed.db
    sid = seed.supplier()
    seed.product("978-1", "А", sid)
    ok, msg = db.add_product("978-1", "Б", "x", sid, 10, 9, 2024, "", "", "")
    assert not ok and "978-1" in msg


def test_update_product(seed):
    db = seed.db
    sid = seed.supplier()
    pid = seed.product("978-1", "Старо", sid, cover=20.0)
    ok, _ = db.update_product(pid, "978-1", "Ново", "Авт", sid, 25.0, 9, 2025,
                              "твърда", "жанр", "опис", critical_minimum=7)
    assert ok
    full = [p for p in db.get_all_products_full() if p["id"] == pid][0]
    assert full["title"] == "Ново" and full["cover_price"] == 25.0
    assert full["critical_minimum"] == 7


def test_delete_product_blocked_with_history(seed):
    db = seed.db
    sid = seed.supplier()
    pid = seed.product("978-1", "Книга", sid)
    seed.deliver(sid, pid, 5, 12.0)                 # създава движение → има история
    ok, msg = db.delete_product(pid)
    assert not ok and "история" in msg


def test_delete_product_ok_without_history(seed):
    db = seed.db
    sid = seed.supplier()
    pid = seed.product("978-1", "Книга", sid)
    ok, _ = db.delete_product(pid)
    assert ok and db.get_all_products_full() == []


def test_product_type_20_percent(seed):
    db = seed.db
    sid = seed.supplier()
    seed.product("MG", "Чаша", sid, cover=24.0, product_type="Стока",
                 fiscal_group="В", vat=20)
    p = [x for x in db.get_all_products_full() if x["isbn"] == "MG"][0]
    assert p["fiscal_group"] == "В" and p["vat_rate"] == 20


# ---------- ДОСИЕ ----------

def test_product_dossier_histories(seed):
    db = seed.db
    sid = seed.supplier()
    pid = seed.product("978-1", "Книга", sid)
    seed.deliver(sid, pid, 10, 12.0, doc="F1")
    seed.deliver(sid, pid, 5, 13.0, doc="F2", date="2026-06-05")
    db.create_sale("ORD1", "w", [{"product_id": pid, "title": "Книга",
                                  "quantity": 3, "cost_price": 12.0,
                                  "sale_price": 20.0}], "В брой (Каса)")
    dh = db.get_product_delivery_history(pid)
    assert len(dh) == 2 and sum(r["quantity"] for r in dh) == 15
    sh = db.get_product_sales_history(pid)
    assert len(sh) == 1 and sh[0]["quantity"] == 3
    assert db.get_current_stock(pid) == 12          # 15 доставени − 3 продадени
