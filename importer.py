"""
Импорт на продажби от онлайн магазина (Excel/CSV) и генериране на заявки за
зареждане, групирани по доставчик.

Чисти функции върху pandas — без Streamlit и без директен достъп до базата.
Четенето на файла идва отвън (Streamlit uploader), а съответствието с каталога
се подава като 'lookup' речник. Така логиката е лесна за тест.
"""
import pandas as pd


# Възможни имена на колоните във файла (сравняват се в lower/strip вид).
# Така приемаме експорти от различни платформи без ръчно мапване.
ISBN_ALIASES = ["isbn", "isbn/баркод", "баркод", "barcode", "ean", "ean13",
                "isbn13", "код", "sku", "product code", "артикул"]
QTY_ALIASES = ["количество", "брой", "бройки", "quantity", "qty",
               "продадено количество", "продадени", "sold", "count"]
PRICE_ALIASES = ["продажна цена", "sale price", "unit price", "единична цена",
                 "продажна", "price", "цена", "корична цена", "корична"]
TITLE_ALIASES = ["заглавие", "title", "наименование", "име на продукта",
                 "product name", "name", "продукт", "книга"]


def read_sales_file(uploaded_file):
    """Чете качения файл в pandas DataFrame според разширението му."""
    name = (getattr(uploaded_file, "name", "") or "").lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    return pd.read_excel(uploaded_file)


def _find_column(columns, aliases):
    """Намира оригиналното име на колона, чийто нормализиран вид съвпада
    (точно или частично) с някой от подадените алиаси."""
    norm = {str(c).strip().lower(): c for c in columns}
    for a in aliases:                      # първо точно съвпадение
        if a in norm:
            return norm[a]
    for key, orig in norm.items():         # после частично (съдържа алиаса)
        if any(a in key for a in aliases):
            return orig
    return None


def detect_columns(df):
    """Връща {'isbn':col, 'qty':col, 'price':col}; някоя стойност може да е None."""
    return {
        "isbn": _find_column(df.columns, ISBN_ALIASES),
        "qty": _find_column(df.columns, QTY_ALIASES),
        "price": _find_column(df.columns, PRICE_ALIASES),
        "title": _find_column(df.columns, TITLE_ALIASES),
    }


def clean_isbn(value):
    """Нормализира ISBN: Excel често чете баркода като число (9.78e+12 или
    '9780000000001.0') — връщаме чист низ без '.0' и интервали."""
    if value is None:
        return ""
    if isinstance(value, float):
        if pd.isna(value):
            return ""
        if value.is_integer():
            return str(int(value))
    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def parse_rows(df, cols):
    """
    Превръща DataFrame в списък {isbn, qty, sale_price}, агрегиран по ISBN
    (един и същ ISBN на няколко реда се сумира). Пропуска редове без ISBN
    или с количество <= 0.
    """
    isbn_col = cols.get("isbn")
    qty_col = cols.get("qty")
    price_col = cols.get("price")
    title_col = cols.get("title")

    agg = {}
    for _, row in df.iterrows():
        isbn = clean_isbn(row[isbn_col]) if isbn_col is not None else ""
        if not isbn:
            continue
        try:
            qty = int(float(row[qty_col])) if qty_col is not None else 0
        except (ValueError, TypeError):
            qty = 0
        if qty <= 0:
            continue
        sale_price = None
        if price_col is not None:
            try:
                sale_price = float(row[price_col])
            except (ValueError, TypeError):
                sale_price = None
        # Заглавие от файла (за непознатите ISBN-и, които ще се създават).
        title = ""
        if title_col is not None:
            tv = row[title_col]
            if not (tv is None or (isinstance(tv, float) and pd.isna(tv))):
                title = str(tv).strip()

        entry = agg.setdefault(isbn, {"isbn": isbn, "qty": 0,
                                      "sale_price": sale_price, "title": title})
        if not entry.get("title") and title:   # пазим първото непразно заглавие
            entry["title"] = title
        entry["qty"] += qty
    return list(agg.values())


def group_by_supplier(parsed_rows, lookup):
    """
    Групира редовете по доставчик чрез lookup ({isbn: product_info от базата}).

    Връща (groups, unmatched):
      groups = {supplier_id: {supplier_id, name, email, items[], total_qty,
                              total_delivery}}
      unmatched = [isbn, ...]  — ISBN-и от файла, които липсват в каталога.
    """
    groups = {}
    unmatched = []
    for r in parsed_rows:
        info = lookup.get(r["isbn"])
        if info is None:
            # Непознат ISBN — връщаме наличната от файла информация, за да може
            # потребителят бързо да го създаде (ISBN, заглавие, корична цена).
            unmatched.append({
                "isbn": r["isbn"],
                "title": r.get("title") or "",
                "cover_price": r.get("sale_price") or 0.0,
                "qty": r["qty"],
            })
            continue
        # Единична доставна цена: последната доставна цена, а ако книгата още
        # няма доставки (напр. току-що създадена) — оценка от стандартната
        # отстъпка на доставчика върху коричната цена.
        last_cost = info.get("last_cost") or 0
        if last_cost:
            unit_cost = round(last_cost, 2)
        else:
            disc = info.get("default_discount") or 0
            unit_cost = round((info.get("cover_price") or 0) * (1 - disc / 100), 2)

        g = groups.setdefault(info["supplier_id"], {
            "supplier_id": info["supplier_id"],
            "name": info["supplier_name"],
            "email": info["supplier_email"],
            "items": [],
            "total_qty": 0,
            "total_delivery": 0.0,
        })
        line_delivery = round(r["qty"] * unit_cost, 2)
        g["items"].append({
            "isbn": info["isbn"],
            "title": info["title"],
            "author": info["author"],
            "delivery_price": unit_cost,
            "cover_price": info["cover_price"],
            "qty": r["qty"],
            "line_delivery": line_delivery,
        })
        g["total_qty"] += r["qty"]
        g["total_delivery"] = round(g["total_delivery"] + line_delivery, 2)
    return groups, unmatched
