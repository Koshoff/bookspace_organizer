"""
Създава оператор (по подразбиране администратор) в bookspace.db.
Паролата се въвежда скрито — не остава в историята на терминала.

Употреба:
    python backend/create_admin.py                 # интерактивно
    python backend/create_admin.py --username ivo --role admin
"""
import argparse
import getpass
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, "backend"))

import db.connection
db.connection.DB_FILE = os.environ.get(
    "BOOKSPACE_DB", os.path.join(_REPO_ROOT, "bookspace.db")
)

from app import operators  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Създаване на оператор")
    ap.add_argument("--username")
    ap.add_argument("--full-name", default="")
    ap.add_argument("--role", default="admin", choices=list(operators.ROLES))
    args = ap.parse_args()

    operators.ensure_table()

    username = args.username or input("Потребителско име: ").strip()
    if operators.get_by_username(username):
        print(f"⚠️ Оператор „{username}“ вече съществува.")
        sys.exit(1)

    pwd = getpass.getpass("Парола (мин. 6 знака): ")
    pwd2 = getpass.getpass("Повтори паролата: ")
    if pwd != pwd2:
        print("⚠️ Паролите не съвпадат.")
        sys.exit(1)

    ok, msg = operators.create_operator(username, pwd, args.full_name, args.role)
    print(("✅ " if ok else "⚠️ ") + msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
