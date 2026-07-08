"""
Масово засичане на куриерски отчети (Спиди/Еконт) срещу продажбите в Bookspace.

Чисти функции (без Streamlit): парсване на текст/файл и финансов одит.
Свързването с базата се подава като 'lookup' речник {waybill: sale_info}.
"""
import re

import pandas as pd


WAYBILL_ALIASES = ["товарителница", "товар", "номер", "tracking", "колет",
                   "пратка", "barcode", "number", "№", "код"]
AMOUNT_ALIASES = ["сума", "наложен платеж", "наложенплатеж", "cod", "amount",
                  "събрана", "стойност", "получаване", "sum", "value"]


def parse_amount(value):
    """Превръща '12,50', '12.50', '1 234,00 лв.' → float. None при неуспех."""
    if value is None:
        return None
    s = str(value).strip().replace(" ", "").replace(" ", "")
    s = s.replace("лв.", "").replace("лв", "").replace("BGN", "")
    if not s:
        return None
    # И запетая, и точка → запетаята е разделител на хиляди.
    if "," in s and "." in s:
        s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _extract_amount(rest):
    """Изважда сумата от остатъка на реда: маха валута/текст, слепва интервалите
    между цифри (разделител на хиляди) и взима ПОСЛЕДНОТО число."""
    r = str(rest).replace("лв.", "").replace("лв", "").replace("BGN", "")
    r = re.sub(r"(?<=\d)[  ](?=\d)", "", r)   # „1 234" → „1234"
    nums = re.findall(r"\d+(?:[.,]\d+)?", r)
    return parse_amount(nums[-1]) if nums else None


def parse_courier_text(text):
    """
    Парсва поставен текст, ред по ред: 'номер_товарителница сума'.
    Номерът е първата „дума"; сумата се извлича от останалата част (толерантно
    към валута, таб, ';' и разделител на хиляди). Връща [(waybill, amount)].
    За чист CSV с десетична запетая ползвай File Uploader-а.
    """
    pairs = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        # Номерът е водещият низ до първия разделител (интервал/таб/';'/','),
        # останалото е сумата. Така работи и за comma-separated редове.
        m = re.match(r"^\s*([^\s,;]+)[\s,;]+(.*)$", line)
        if not m:
            continue
        waybill = m.group(1).strip()
        amount = _extract_amount(m.group(2))
        if waybill and amount is not None:
            pairs.append((waybill, amount))
    return pairs


def _find_column(columns, aliases):
    norm = {str(c).strip().lower(): c for c in columns}
    for a in aliases:
        if a in norm:
            return norm[a]
    for key, orig in norm.items():
        if any(a in key for a in aliases):
            return orig
    return None


def parse_courier_file(uploaded_file):
    """Чете Excel/CSV отчет от куриера и връща [(waybill, amount)]."""
    name = (getattr(uploaded_file, "name", "") or "").lower()
    if name.endswith(".csv"):
        # sep=None разпознава разделителя (',' или ';').
        df = pd.read_csv(uploaded_file, sep=None, engine="python")
    else:
        df = pd.read_excel(uploaded_file)

    wcol = _find_column(df.columns, WAYBILL_ALIASES)
    acol = _find_column(df.columns, AMOUNT_ALIASES)
    if wcol is None or acol is None:
        return [], (wcol, acol)

    pairs = []
    for _, row in df.iterrows():
        wb = str(row[wcol]).strip()
        if wb.endswith(".0"):        # Excel чете номера като число
            wb = wb[:-2]
        amt = parse_amount(row[acol])
        if wb and wb.lower() != "nan" and amt is not None:
            pairs.append((wb, amt))
    return pairs, (wcol, acol)


def reconcile(pairs, lookup, tol=0.005):
    """
    Финансов одит: за всяка товарителница сравнява сумата от куриера с
    продажната сума в Bookspace (lookup[waybill]['total']).

    Връща речник:
      matched    — точно съвпадение (до стотинка),
      mismatched — има поръчка, но сумата се разминава (с 'diff' = куриер − Bookspace),
      unknown    — товарителницата липсва в базата,
      total_received — общата сума от куриера.
    Дубликатите на товарителница се засичат само веднъж.
    """
    matched, mismatched, unknown = [], [], []
    total = 0.0
    seen = set()
    for waybill, amount in pairs:
        if waybill in seen:
            continue
        seen.add(waybill)
        total += amount
        info = lookup.get(waybill)
        if info is None:
            unknown.append({"waybill": waybill, "speedy": round(amount, 2)})
            continue
        book = round(info["total"], 2)
        rec = {
            "waybill": waybill,
            "order_number": info["order_number"] or "-",
            "sale_id": info["id"],
            "status": info["status"],
            "bookspace": book,
            "speedy": round(amount, 2),
        }
        if abs(book - amount) <= tol:
            matched.append(rec)
        else:
            rec["diff"] = round(amount - book, 2)
            mismatched.append(rec)
    return {
        "matched": matched,
        "mismatched": mismatched,
        "unknown": unknown,
        "total_received": round(total, 2),
    }
