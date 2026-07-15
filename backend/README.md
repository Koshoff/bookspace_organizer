# Bookspace API (FastAPI)

Backend слой, който увива съществуващия `db/` пакет и обслужва бъдещия React
фронтенд. Бизнес логиката НЕ се дублира — endpoint-ите викат `db.*`.

## Модел на сигурност

- **Тайните никога не са в кода или в git.** Всичко идва от `backend/.env`
  (в `.gitignore`). Виж `.env.example`.
- **Паролите** се пазят само като bcrypt хеш (`passlib`), никога в чист текст.
- **Токените** (JWT) се доставят като `httpOnly` + `Secure` + `SameSite`
  cookies — JavaScript не може да ги чете, така XSS не ги краде.
- **CORS** е заключен за точния origin на фронтенда, не `*`.
- **Login** е rate-limited (5/минута) срещу brute force.
- **Без user enumeration** — грешно име и грешна парола дават еднакъв отговор.
- Всички външни услуги (SMTP и т.н.) се викат от сървъра с тайни, които
  никога не стигат браузъра.

## Пускане

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # или .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # сложи го в SECRET_KEY

# създай първия администратор
python create_admin.py --username admin --role admin

# старт
uvicorn app.main:app --reload
```

API-то тръгва на `http://localhost:8000`, документация на `/docs`.

## Endpoint-и (Фаза 1)

| Метод | Път | Достъп | Описание |
|---|---|---|---|
| GET | `/api/health` | публичен | здравна проверка |
| POST | `/api/auth/login` | публичен | вход, връща auth cookies |
| POST | `/api/auth/refresh` | cookie | подновяване на access токена |
| POST | `/api/auth/logout` | — | изтрива cookies |
| GET | `/api/auth/me` | сесия | текущият оператор |
| GET | `/api/catalog/products` | сесия | всички артикули с наличност |
| GET | `/api/catalog/products/{isbn}` | сесия | артикул по ISBN |
| GET | `/api/dashboard` | сесия | обобщени показатели за период |
