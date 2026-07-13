"""
Еднократен импорт на ПРОДУКТОВ КАТАЛОГ (номенклатура) от Excel/CSV.

Всеки ред = една книга, която се създава в каталога с наличност 0 (БЕЗ количество).
Разпознати колони (толерантно към имената): Производител/Издателство → доставчик,
Наименование → заглавие, Баркод → ISBN, Цена → корична, Отст. → отстъпка,
ДДС → ставка, Общо → доставна цена. Липсващите доставчици се създават.

Употреба:
    python scripts/import_catalog.py файл.xlsx --dry-run     # само отчита
    python scripts/import_catalog.py файл.xlsx               # реален запис
    python scripts/import_catalog.py файл.xlsx --no-prices   # без историческа доставна цена
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

SUP_ALIASES = ["производител", "издателство", "издател", "доставчик", "supplier"]
TITLE_ALIASES = ["наименование", "заглавие", "име", "title", "продукт", "книга"]
ISBN_ALIASES = ["баркод", "isbn", "код", "barcode", "ean"]
COVER_ALIASES = ["цена", "корична", "cover", "price"]
DISC_ALIASES = ["отст", "отстъпка", "discount", "%"]
VAT_ALIASES = ["ддс", "vat"]
DELIV_ALIASES = ["общо", "доставна", "нето", "net", "total"]


def _find(columns, aliases):
    norm = {str(c).strip().lower(): c for c in columns}
    for a in aliases:
        if a in norm:
            return norm[a]
    for key, orig in norm.items():
        if any(a in key for a in aliases):
            return orig
    return None


def detect_columns(df):
    return {
        "supplier": _find(df.columns, SUP_ALIASES),
        "title": _find(df.columns, TITLE_ALIASES),
        "isbn": _find(df.columns, ISBN_ALIASES),
        "cover": _find(df.columns, COVER_ALIASES),
        "discount": _find(df.columns, DISC_ALIASES),
        "vat": _find(df.columns, VAT_ALIASES),
        "delivery": _find(df.columns, DELIV_ALIASES),
    }


def _num(value):
    """'11,50' / '11.50' / '7,47 лв' → float. None при неуспех."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip().replace(" ", "").replace("лв", "").replace("%", "")
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _pct(value):
    """Процент: приема 35, '35%' или Excel-формат 0.35 → връща 35.0."""
    n = _num(value)
    if n is None:
        return None
    return round(n * 100, 2) if n <= 1 else round(n, 2)


def _clean_isbn(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    s = str(value).strip()
    return s[:-2] if s.endswith(".0") else s


def run_import(df, db, dry_run=False, set_prices=True):
    """Изпълнява импорта. Връща статистика (dict). Не хвърля при проблемен ред —
    трупа предупреждения."""
    cols = detect_columns(df)
    missing = [k for k in ("supplier", "title", "isbn", "cover") if not cols[k]]
    if missing:
        raise ValueError(f"Липсват задължителни колони: {', '.join(missing)}. "
                         f"Открити: {list(df.columns)}")

    suppliers = {s["name"]: s["id"] for s in db.get_all_suppliers()}
    existing_isbns = {p["isbn"] for p in db.get_all_products_full()}
    seen_isbns = set()

    stats = {"products": 0, "suppliers": 0, "skipped": 0, "errors": []}
    price_updates = []   # (isbn, delivery, discount) за след вмъкване

    for i, row in df.iterrows():
        rownum = i + 2   # +1 за 0-индекс, +1 за заглавния ред
        isbn = _clean_isbn(row[cols["isbn"]])
        title = str(row[cols["title"]]).strip() if not (
            isinstance(row[cols["title"]], float) and pd.isna(row[cols["title"]])) else ""
        sup_name = str(row[cols["supplier"]]).strip() if not (
            isinstance(row[cols["supplier"]], float) and pd.isna(row[cols["supplier"]])) else ""
        cover = _num(row[cols["cover"]])
        disc = _pct(row[cols["discount"]]) if cols["discount"] else None
        vat = _pct(row[cols["vat"]]) if cols["vat"] else 9.0
        deliv = _num(row[cols["delivery"]]) if cols["delivery"] else None

        if not isbn or not title or not sup_name:
            stats["errors"].append(f"Ред {rownum}: липсва ISBN/заглавие/доставчик — пропуснат.")
            continue
        if cover is None:
            stats["errors"].append(f"Ред {rownum} ({title}): невалидна цена — пропуснат.")
            continue
        if isbn in existing_isbns or isbn in seen_isbns:
            stats["skipped"] += 1
            continue
        seen_isbns.add(isbn)

        # Доставчик: създаваме при липса (имейл празен → допълва се после).
        if sup_name not in suppliers:
            stats["suppliers"] += 1
            if not dry_run:
                db.add_supplier(sup_name, "", "", "", "", "", disc or 0.0)
                suppliers[sup_name] = [s["id"] for s in db.get_all_suppliers()
                                       if s["name"] == sup_name][0]
            else:
                suppliers[sup_name] = -1   # placeholder за dry-run

        if dry_run:
            stats["products"] += 1
            continue

        ok, msg = db.add_product(isbn, title, "", suppliers[sup_name], cover,
                                 vat or 9.0, 0, "", "", "",
                                 product_type="Книга", fiscal_group="Б")
        if ok:
            stats["products"] += 1
            if set_prices and deliv is not None:
                price_updates.append((isbn, round(deliv, 2), disc))
        else:
            stats["errors"].append(f"Ред {rownum} ({title}): {msg}")

    # Историческа доставна цена/отстъпка от прайс-листа (за prefill в Доставки).
    if not dry_run and price_updates:
        conn = db.get_connection()
        conn.executemany(
            "UPDATE products SET last_delivery_price=?, last_discount_pct=? WHERE isbn=?",
            [(dp, ds, isbn) for isbn, dp, ds in price_updates])
        conn.commit()
        conn.close()

    return stats


def _read(path):
    if path.lower().endswith(".csv"):
        return pd.read_csv(path, sep=None, engine="python")
    return pd.read_excel(path)


def main():
    ap = argparse.ArgumentParser(description="Импорт на продуктов каталог от Excel/CSV")
    ap.add_argument("file", help="път до .xlsx / .csv")
    ap.add_argument("--dry-run", action="store_true", help="само отчита, без запис")
    ap.add_argument("--no-prices", action="store_true",
                    help="не записва историческа доставна цена")
    args = ap.parse_args()

    import db
    df = _read(args.file)
    print(f"Прочетени {len(df)} реда. Колони: {list(df.columns)}")
    stats = run_import(df, db, dry_run=args.dry_run, set_prices=not args.no_prices)

    mode = "DRY-RUN (нищо не е записано)" if args.dry_run else "ЗАПИСАНО"
    print(f"\n=== {mode} ===")
    print(f"Нови книги:       {stats['products']}")
    print(f"Нови издателства: {stats['suppliers']}")
    print(f"Пропуснати (дубликат ISBN): {stats['skipped']}")
    if stats["errors"]:
        print(f"\nПредупреждения ({len(stats['errors'])}):")
        for e in stats["errors"][:30]:
            print("  -", e)
        if len(stats["errors"]) > 30:
            print(f"  … и още {len(stats['errors']) - 30}")
    if not args.dry_run:
        print("\n⚠️ Новите издателства са без имейл — допълни ги в раздел Доставчици.")


if __name__ == "__main__":
    main()
