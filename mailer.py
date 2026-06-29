"""
Сервизен слой за автоматичните заявки за зареждане към издателствата.

Държи две неща разделени:
- ЧИСТИ функции за сглобяване на имейла (HTML таблица + тяло) — без Streamlit,
  лесни за тест и за бъдещо реално изпращане.
- send_supplier_email(...) — СИМУЛАЦИЯ на изпращането. Когато се сложи реален
  SMTP, само тялото на тази функция се сменя; интерфейсът остава същият.
"""
import html
import re

import streamlit as st


# Проста, но достатъчна проверка за валиден имейл (не е RFC-пълна нарочно).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(value):
    """Връща True, ако стойността прилича на валиден имейл адрес."""
    return bool(value) and bool(_EMAIL_RE.match(value.strip()))


def build_order_html_table(items):
    """
    Сглобява HTML таблица в стил Sleek Monochrome за заявката.
    'items' е списък от речници с: isbn, title, author, total_sold.
    Стиловете са INLINE нарочно — за да се покажат правилно и в имейл клиент,
    който често игнорира <style> блокове.
    """
    head_cell = ("padding:10px 12px;border:1px solid #1a1a1a;"
                 "background:#1a1a1a;color:#ffffff;text-align:left;"
                 "font-weight:600;font-size:13px;")
    rows_html = []
    for i, it in enumerate(items):
        # Редуваме фона на редовете за по-добра четимост (zebra).
        bg = "#ffffff" if i % 2 == 0 else "#f6f6f6"
        cell = (f"padding:9px 12px;border:1px solid #e0e0e0;"
                f"background:{bg};color:#1a1a1a;font-size:13px;")
        cell_center = cell + "text-align:center;font-weight:600;"
        rows_html.append(
            f"<tr>"
            f"<td style='{cell}'>{html.escape(str(it['isbn']))}</td>"
            f"<td style='{cell}'>{html.escape(str(it['title']))}</td>"
            f"<td style='{cell}'>{html.escape(str(it['author'] or '-'))}</td>"
            f"<td style='{cell_center}'>{int(it['total_sold'])}</td>"
            f"</tr>"
        )

    return (
        "<table style='border-collapse:collapse;width:100%;"
        "font-family:Arial,Helvetica,sans-serif;'>"
        "<thead><tr>"
        f"<th style='{head_cell}'>ISBN</th>"
        f"<th style='{head_cell}'>Заглавие</th>"
        f"<th style='{head_cell}'>Автор</th>"
        f"<th style='{head_cell};text-align:center'>Заявка за зареждане (бр.)</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table>"
    )


def build_order_email_html(supplier_name, day_str, table_html):
    """
    Връща пълното HTML тяло на официалния имейл на чист български език.
    Таблицата (table_html) се вмъква на мястото си в шаблона.
    """
    safe_name = html.escape(str(supplier_name))
    return (
        "<div style='font-family:Arial,Helvetica,sans-serif;color:#1a1a1a;"
        "font-size:14px;line-height:1.55;'>"
        f"<p>Здравейте, Екип на {safe_name},</p>"
        "<p>Прикачено изпращаме автоматичен отчет за продадените книги от вашия "
        "каталог в търговските обекти и сайта на Bookspace за дата "
        f"<strong>{html.escape(str(day_str))}</strong>.</p>"
        "<p>Моля, подгответе и ни изпратете следните бройки за запълване на "
        "наличностите:</p>"
        f"{table_html}"
        "<p style='margin-top:18px;'>Поздрави,<br>Екипът на Bookspace</p>"
        "</div>"
    )


def send_supplier_email(supplier_name, email, html_table):
    """
    СИМУЛАЦИЯ на изпращането на заявка към доставчик.

    За реално изпращане тук би влязъл SMTP (smtplib + EmailMessage с
    HTML съдържанието). Засега само потвърждаваме на екрана със зелено
    съобщение в заоблен контейнер и връщаме True за управление на потока.
    """
    st.success(
        f"✅ Успешно изпратена поръчка до {supplier_name} на имейл: {email}!"
    )
    return True
