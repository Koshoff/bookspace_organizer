"""Тест за еднократния импорт на продуктов каталог (scripts/import_catalog.py)."""
import importlib.util
import os

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_module():
    path = os.path.join(ROOT, "scripts", "import_catalog.py")
    spec = importlib.util.spec_from_file_location("import_catalog", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sample_df():
    # Реплика на клиентския файл (Отст./ДДС като текст с %).
    return pd.DataFrame({
        "Производител": ["AMG", "AMG", "DUO DESIGN"],
        "Наименование": ["БЕЗРАСЪДЕН КУРАЖ", "ЛЪЖКИНЯТА", "БАБАТА БАНДИТ 1"],
        "Баркод": ["9786197831009", "9786197831085", "9789548396639"],
        "Кол.": [1, 1, 1],
        "Цена": [11.50, 12.99, 14.80],
        "Отст.": ["35%", "35%", "30%"],
        "ДДС": ["9%", "9%", "9%"],
        "Общо": [7.47, 8.44, 10.36],
    })


def test_detect_columns():
    m = _load_module()
    cols = m.detect_columns(_sample_df())
    assert cols["supplier"] == "Производител"
    assert cols["title"] == "Наименование"
    assert cols["isbn"] == "Баркод"
    assert cols["cover"] == "Цена"
    assert cols["delivery"] == "Общо"


def test_pct_and_num_helpers():
    m = _load_module()
    assert m._pct("35%") == 35.0
    assert m._pct(0.35) == 35.0          # Excel percent-формат
    assert m._pct(9) == 9.0
    assert m._num("11,50") == 11.50
    assert m._num("7.47 лв") == 7.47


def test_dry_run_counts_without_writing(fresh_db):
    m = _load_module()
    stats = m.run_import(_sample_df(), fresh_db, dry_run=True)
    assert stats["products"] == 3 and stats["suppliers"] == 2
    assert fresh_db.get_all_products_full() == []      # нищо не е записано


def test_real_import_creates_catalog_zero_stock(fresh_db):
    m = _load_module()
    stats = m.run_import(_sample_df(), fresh_db, dry_run=False)
    assert stats["products"] == 3 and stats["suppliers"] == 2 and stats["errors"] == []

    p = [x for x in fresh_db.get_all_products_full() if x["isbn"] == "9786197831009"][0]
    assert p["cover_price"] == 11.50               # „Цена" → корична
    assert p["last_delivery_price"] == 7.47        # „Общо" → доставна
    assert p["last_discount_pct"] == 35.0
    assert fresh_db.get_current_stock(p["id"]) == 0  # каталог БЕЗ количество

    sup = [s for s in fresh_db.get_all_suppliers() if s["name"] == "DUO DESIGN"][0]
    assert sup["default_discount"] == 30.0


def test_reimport_is_idempotent(fresh_db):
    m = _load_module()
    m.run_import(_sample_df(), fresh_db, dry_run=False)
    again = m.run_import(_sample_df(), fresh_db, dry_run=False)
    assert again["products"] == 0 and again["skipped"] == 3


def test_missing_required_column_raises(fresh_db):
    m = _load_module()
    bad = pd.DataFrame({"Наименование": ["X"], "Цена": [1.0]})  # няма доставчик/ISBN
    with pytest.raises(ValueError):
        m.run_import(bad, fresh_db)
