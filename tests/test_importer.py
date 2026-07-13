"""Тестове за importer.py: разпознаване на колони, ISBN, засичане по ISBN/заглавие."""
import io

import pandas as pd
import pytest

import importer


class FakeUpload(io.BytesIO):
    def __init__(self, data, name):
        super().__init__(data)
        self.name = name


def _catalog():
    return [
        {"id": 1, "isbn": "9780000000001", "title": "Под игото", "author": "Вазов",
         "cover_price": 20.0, "supplier_id": 1, "supplier_name": "Сиела",
         "supplier_email": "a@ciela.bg", "default_discount": 40.0, "last_cost": 0},
        {"id": 2, "isbn": "9780000000002", "title": "Време разделно", "author": "Хайтов",
         "cover_price": 18.0, "supplier_id": 2, "supplier_name": "Колибри",
         "supplier_email": "b@colibri.bg", "default_discount": 35.0, "last_cost": 7.0},
        {"id": 3, "isbn": "9780000000003", "title": "Тютюн", "author": "Димов",
         "cover_price": 25.0, "supplier_id": 1, "supplier_name": "Сиела",
         "supplier_email": "a@ciela.bg", "default_discount": 40.0, "last_cost": 0},
    ]


def test_clean_isbn():
    assert importer.clean_isbn(9780000000001.0) == "9780000000001"
    assert importer.clean_isbn("9780000000001.0") == "9780000000001"
    assert importer.clean_isbn("  978-1 ") == "978-1"
    assert importer.clean_isbn(float("nan")) == ""


def test_detect_columns_bulgarian_headers():
    df = pd.DataFrame({"ISBN/Баркод": [], "Продадено количество": [],
                       "Продажна цена": [], "Заглавие": []})
    cols = importer.detect_columns(df)
    assert cols["isbn"] == "ISBN/Баркод"
    assert cols["qty"] == "Продадено количество"
    assert cols["title"] == "Заглавие"


def test_parse_rows_aggregates_by_isbn():
    df = pd.DataFrame({
        "ISBN": [9780000000001.0, 9780000000001.0, 9780000000002.0],
        "Количество": [2, 3, 1],
    })
    cols = importer.detect_columns(df)
    parsed = importer.parse_rows(df, cols)
    d = {p["isbn"]: p["qty"] for p in parsed}
    assert d == {"9780000000001": 5, "9780000000002": 1}


def test_resolve_rows_isbn_and_title():
    parsed = [
        {"isbn": "9780000000002", "qty": 2, "title": "", "sale_price": None},
        {"isbn": "", "qty": 3, "title": "Под игото (юбилейно издание)", "sale_price": None},
        {"isbn": "", "qty": 4, "title": "Тютюн", "sale_price": None},
        {"isbn": "", "qty": 1, "title": "Време", "sale_price": None},   # едно-думно → двусмислено
        {"isbn": "999", "qty": 5, "title": "Нещо ново", "sale_price": None},
    ]
    matched, unmatched = importer.resolve_rows(parsed, _catalog())
    methods = {m["product"]["id"]: m["method"] for m in matched}
    assert methods == {2: "isbn", 1: "title", 3: "title"}
    assert sorted(u["title"] for u in unmatched) == ["Време", "Нещо ново"]


def test_group_matched_discount_estimate_and_last_cost():
    parsed = [
        {"isbn": "9780000000001", "qty": 3, "title": "", "sale_price": None},  # last_cost 0 → оценка
        {"isbn": "9780000000002", "qty": 2, "title": "", "sale_price": None},  # last_cost 7
    ]
    matched, _ = importer.resolve_rows(parsed, _catalog())
    groups = importer.group_matched(matched)
    # Сиела: 20*(1-40/100)=12 → 3*12=36 ; Колибри: last_cost 7 → 2*7=14
    assert groups[1]["total_delivery"] == 36.0
    assert groups[2]["total_delivery"] == 14.0


def test_read_sales_file_csv_semicolon():
    data = "ISBN;Количество\n9780000000001;2\n9780000000002;3\n".encode("utf-8")
    df = importer.read_sales_file(FakeUpload(data, "report.csv"))
    cols = importer.detect_columns(df)
    parsed = importer.parse_rows(df, cols)
    assert {p["isbn"]: p["qty"] for p in parsed} == {"9780000000001": 2, "9780000000002": 3}


def test_read_sales_file_xlsx():
    buf = io.BytesIO()
    pd.DataFrame({"ISBN": ["978-1"], "Количество": [4]}).to_excel(buf, index=False)
    df = importer.read_sales_file(FakeUpload(buf.getvalue(), "report.xlsx"))
    parsed = importer.parse_rows(df, importer.detect_columns(df))
    assert parsed[0]["isbn"] == "978-1" and parsed[0]["qty"] == 4
