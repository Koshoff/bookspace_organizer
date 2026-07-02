"""
Локален файлов архив за прикачените фактури (снимки/PDF).
Записва качения файл в папка uploaded_invoices/ с име по номера на доставката.
"""
import os
import re

INVOICE_DIR = "uploaded_invoices"


def _safe_name(name):
    """Прави безопасно име на файл: маха проблемни символи (напр. „/" в номер)."""
    cleaned = re.sub(r"[^0-9A-Za-zА-Яа-я._-]+", "_", str(name or "")).strip("_")
    return cleaned or "faktura"


def save_invoice_file(uploaded_file, doc_number, directory=INVOICE_DIR):
    """
    Записва Streamlit UploadedFile в 'directory' с име по номера на доставката.
    При колизия добавя суфикс _2, _3, … Връща относителния път до файла.
    """
    os.makedirs(directory, exist_ok=True)
    ext = os.path.splitext(uploaded_file.name)[1].lower() or ".bin"
    base = _safe_name(doc_number)
    path = os.path.join(directory, base + ext)
    i = 2
    while os.path.exists(path):
        path = os.path.join(directory, f"{base}_{i}{ext}")
        i += 1
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return path
