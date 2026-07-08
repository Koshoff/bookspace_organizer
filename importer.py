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
        # sep=None + engine='python' разпознава разделителя (',' или ';' —
        # българските Excel експорти често са с ';').
        return pd.read_csv(uploaded_file, sep=None, engine="python")
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


# ---------- ЗАСИЧАНЕ В ПАМЕТТА (по ISBN и по заглавие) ----------
# Кратки/служебни думи, които не носят смисъл при сравнение на заглавия.
# Само истински служебни думи — НЕ махаме думи, които могат да са част от
# заглавие (напр. „под“ в „Под игото“), за да не осакатим късите заглавия.
_STOPWORDS = {
    "и", "на", "за", "от", "или", "the", "a", "an", "of", "and", "or",
}


def normalize_title(value):
    """Нормализира заглавие за сравнение: малки букви, без пунктуация/цифри-шум,
    единични интервали. Работи и за кирилица, и за латиница."""
    s = str(value or "").lower()
    out = []
    for ch in s:
        if ch.isalnum():          # буква или цифра (вкл. кирилица)
            out.append(ch)
        else:
            out.append(" ")
    return " ".join("".join(out).split())


def title_tokens(value):
    """Множество от значими думи в заглавие (>=3 символа, без стоп-думи)."""
    return {t for t in normalize_title(value).split()
            if len(t) >= 3 and t not in _STOPWORDS}


def build_catalog_index(catalog):
    """
    Строи индексите за бързо засичане ВЕДНЪЖ:
      - isbn_index: {clean_isbn: product}
      - title_index: [(token_set, product), ...]
    """
    isbn_index = {}
    title_index = []
    for p in catalog:
        key = clean_isbn(p.get("isbn"))
        if key:
            isbn_index[key] = p
        # Пазим и нормализирания вид — нужен за точно сравнение на едно-думни
        # заглавия (където припокриването на думи е твърде слаб сигнал).
        title_index.append((title_tokens(p.get("title")),
                            normalize_title(p.get("title")), p))
    return isbn_index, title_index


def _best_title_match(file_title, title_index, min_score):
    """
    Намира най-доброто съвпадение по заглавие чрез припокриване на значими думи.
    КОНСЕРВАТИВНО, за да не лепне грешна книга:
      - при заглавия с >=2 значими думи: иска поне 2 общи думи;
      - при едно-думни заглавия: иска ТОЧНО равенство на нормализирания текст
        (иначе „Време" би лепнало „Време разделно");
      - накрая: резултат >= min_score и ясен лидер пред втория кандидат.
    """
    ftok = title_tokens(file_title)
    if not ftok:
        return None
    fnorm = normalize_title(file_title)
    best, best_score, second_score = None, 0.0, 0.0
    for ctok, cnorm, p in title_index:
        inter = len(ftok & ctok)
        if inter == 0:
            continue
        min_len = min(len(ftok), len(ctok))
        if min_len >= 2:
            if inter < 2:
                continue
            score = max(inter / len(ftok | ctok), inter / min_len)
        else:
            # едно от заглавията е едно-думно — приемаме само точно съвпадение
            if fnorm != cnorm:
                continue
            score = 1.0
        if score > best_score:
            best, second_score, best_score = p, best_score, score
        elif score > second_score:
            second_score = score
    if best_score >= min_score and (best_score - second_score) >= 0.1:
        return best
    return None


def resolve_rows(parsed_rows, catalog, min_score=0.6):
    """
    Засича всеки ред от файла срещу каталога — първо по точен ISBN, после по
    заглавие (в паметта, без заявка на ред). Връща (matched, unmatched):
      matched   = [{product, qty, method}]  (method = 'isbn' | 'title')
      unmatched = [{isbn, title, qty, cover_price}]  — за буферния панел.
    """
    isbn_index, title_index = build_catalog_index(catalog)
    matched, unmatched = [], []
    for r in parsed_rows:
        product, method = None, None
        isbn = r.get("isbn")
        if isbn and isbn in isbn_index:
            product, method = isbn_index[isbn], "isbn"
        elif r.get("title"):
            cand = _best_title_match(r["title"], title_index, min_score)
            if cand is not None:
                product, method = cand, "title"

        if product is None:
            unmatched.append({
                "isbn": r.get("isbn") or "",
                "title": r.get("title") or "",
                "qty": r["qty"],
                "cover_price": r.get("sale_price") or 0.0,
            })
        else:
            matched.append({"product": product, "qty": r["qty"], "method": method})
    return matched, unmatched


def _unit_delivery_cost(product):
    """Единична доставна цена: последната реална доставна цена, а ако книгата
    още няма доставки — оценка от стандартната отстъпка върху коричната."""
    last_cost = product.get("last_cost") or 0
    if last_cost:
        return round(last_cost, 2)
    disc = product.get("default_discount") or 0
    return round((product.get("cover_price") or 0) * (1 - disc / 100), 2)


def group_matched(matched):
    """
    Групира засечените продукти по доставчик. Коричната цена идва от каталога
    (файлът няма цени), а доставната се изчислява чрез _unit_delivery_cost.

    Връща {supplier_id: {supplier_id, name, email, items[], total_qty,
                         total_delivery}}.
    """
    groups = {}
    for m in matched:
        p, qty = m["product"], m["qty"]
        unit_cost = _unit_delivery_cost(p)
        g = groups.setdefault(p["supplier_id"], {
            "supplier_id": p["supplier_id"],
            "name": p["supplier_name"],
            "email": p["supplier_email"],
            "items": [],
            "total_qty": 0,
            "total_delivery": 0.0,
        })
        line_delivery = round(qty * unit_cost, 2)
        g["items"].append({
            "isbn": p["isbn"],
            "title": p["title"],
            "author": p["author"],
            "delivery_price": unit_cost,
            "cover_price": p["cover_price"],
            "qty": qty,
            "line_delivery": line_delivery,
            "method": m["method"],
        })
        g["total_qty"] += qty
        g["total_delivery"] = round(g["total_delivery"] + line_delivery, 2)
    return groups
