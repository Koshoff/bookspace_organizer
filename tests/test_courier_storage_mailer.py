"""Тестове за courier.py (парсване/одит), storage.py (архив), mailer.py (имейл)."""
import io

import pandas as pd

import courier
import storage
import mailer


class FakeUpload(io.BytesIO):
    def __init__(self, data, name):
        super().__init__(data)
        self.name = name


# ---------- COURIER ----------

def test_parse_amount_variants():
    assert courier.parse_amount("12,50") == 12.50
    assert courier.parse_amount("12.50") == 12.50
    assert courier.parse_amount("1 234,00 лв.") == 1234.00
    assert courier.parse_amount("") is None
    assert courier.parse_amount("боклук") is None


def test_parse_text_separators():
    txt = ("1111111111 25.90\n"
           "2222222222\t30,00\n"
           "3333333333;12.50 лв.\n"
           "4444444444,99.99\n"          # comma-separated
           "5555555555 1 234,00\n"       # разделител на хиляди
           "boclук")
    d = dict(courier.parse_courier_text(txt))
    assert d == {"1111111111": 25.90, "2222222222": 30.00, "3333333333": 12.50,
                 "4444444444": 99.99, "5555555555": 1234.00}


def test_reconcile_buckets():
    pairs = [("A", 25.90), ("B", 30.00), ("C", 12.50), ("A", 25.90)]  # дубликат A
    lookup = {
        "A": {"id": 1, "order_number": "O1", "status": "Чака плащане", "total": 25.90},
        "B": {"id": 2, "order_number": "O2", "status": "Чака плащане", "total": 28.00},
    }
    a = courier.reconcile(pairs, lookup)
    assert len(a["matched"]) == 1 and a["matched"][0]["order_number"] == "O1"
    assert len(a["mismatched"]) == 1 and a["mismatched"][0]["diff"] == 2.0
    assert [u["waybill"] for u in a["unknown"]] == ["C"]
    # дубликатът A се брои веднъж
    assert abs(a["total_received"] - (25.90 + 30.00 + 12.50)) < 0.01


def test_parse_courier_file_csv():
    data = "Товарителница;Сума\n111;25,90\n222;30.00\n".encode("utf-8")
    pairs, cols = courier.parse_courier_file(FakeUpload(data, "speedy.csv"))
    assert dict(pairs) == {"111": 25.90, "222": 30.00}


def test_parse_courier_file_missing_columns():
    data = "col1;col2\n1;2\n".encode("utf-8")
    pairs, cols = courier.parse_courier_file(FakeUpload(data, "x.csv"))
    assert pairs == [] and cols == (None, None)


# ---------- STORAGE ----------

def test_save_invoice_file_sanitizes_and_avoids_collision(tmp_path):
    d = str(tmp_path / "inv")
    p1 = storage.save_invoice_file(FakeUpload(b"abc", "photo.JPG"), "INV/77", directory=d)
    p2 = storage.save_invoice_file(FakeUpload(b"def", "photo.jpg"), "INV/77", directory=d)
    assert p1.endswith("INV_77.jpg")            # „/" санитизиран, разширението надолу
    assert p2.endswith("INV_77_2.jpg")          # колизия → суфикс
    import os
    assert os.path.exists(p1) and os.path.exists(p2)


def test_save_invoice_file_empty_docnumber(tmp_path):
    d = str(tmp_path / "inv")
    p = storage.save_invoice_file(FakeUpload(b"x", "a.pdf"), "", directory=d)
    assert p.endswith("faktura.pdf")


# ---------- MAILER ----------

def test_is_valid_email():
    assert mailer.is_valid_email("office@ciela.bg")
    assert mailer.is_valid_email("  spaced@x.bg  ")
    assert not mailer.is_valid_email("")
    assert not mailer.is_valid_email("nope")


def test_build_order_html_table_escapes_and_shows_qty():
    items = [{"isbn": "978-1", "title": "Книга <b>A</b>", "author": None,
              "total_sold": 3}]
    html = mailer.build_order_html_table(items)
    assert "&lt;b&gt;" in html          # заглавието е екранирано
    assert ">-<" in html                # None автор → „-"
    assert "978-1" in html and ">3<" in html


def test_build_order_email_html_template():
    tbl = mailer.build_order_html_table(
        [{"isbn": "1", "title": "T", "author": "A", "total_sold": 1}])
    body = mailer.build_order_email_html("Сиела", "2026-06-20", tbl)
    assert "Здравейте, Екип на Сиела" in body
    assert "2026-06-20" in body and "Екипът на Bookspace" in body


def test_send_supplier_email_returns_true():
    assert mailer.send_supplier_email("Сиела", "a@ciela.bg", "<table></table>") is True
