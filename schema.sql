-- ============================================================
-- ВКЛЮЧВАМЕ ПРОВЕРКАТА НА ВЪНШНИТЕ КЛЮЧОВЕ
-- SQLite по подразбиране НЕ налага foreign keys (исторически по подразбиране).
-- Този ред трябва да се изпълнява при ВСЯКА връзка, иначе релациите са само
-- "документация", а не реално ограничение. Ще го пуснем и от Python.
-- ============================================================
PRAGMA foreign_keys = ON;

-- ============================================================
-- ТАБЛИЦА 1: ДОСТАВЧИЦИ (Модул 1)
-- Стои самостоятелно — от нищо не зависи. Затова я създаваме първа.
-- ============================================================
CREATE TABLE IF NOT EXISTS suppliers (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL UNIQUE,
    bulstat         TEXT,
    mol             TEXT,
    address         TEXT,
    phone           TEXT,
    email           TEXT,
    default_discount REAL   NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ============================================================
-- ТАБЛИЦА 2: ПРОДУКТИ / КНИГИ (Модул 2)
-- Зависи от suppliers — всяка книга има задължителен доставчик.
-- ЗАБЕЛЕЖКА: НЯМА поле за наличност. Тя се смята от stock_movements.
-- ============================================================
CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY,
    isbn            TEXT    NOT NULL UNIQUE,
    title           TEXT    NOT NULL,
    author          TEXT,
    supplier_id     INTEGER NOT NULL,
    cover_price     REAL    NOT NULL,
    vat_rate        REAL    NOT NULL DEFAULT 9,
    year            INTEGER,
    cover_type      TEXT,
    genre           TEXT,
    description     TEXT,
    -- Тип на артикула: 'Книга' или 'Ваучер'. Default за обратна съвместимост.
    product_type    TEXT    NOT NULL DEFAULT 'Книга',
    -- Фискална група за касов апарат: 'Б' (9% ДДС, книги), 'Д' (0%, ваучери).
    fiscal_group    TEXT    NOT NULL DEFAULT 'Б',
    -- Критичен минимум наличност — под него ПОС-ът алармира при продажба.
    critical_minimum INTEGER NOT NULL DEFAULT 3,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

-- ============================================================
-- ТАБЛИЦА 3: ДОСТАВКИ — "КАПАКЪТ" на документа (Модул 3)
-- Един ред = един доставен документ (фактура/разписка/консигнация).
-- Книгите в него са в отделна таблица (delivery_items). Релация 1:много.
-- ============================================================
CREATE TABLE IF NOT EXISTS deliveries (
    id              INTEGER PRIMARY KEY,
    supplier_id     INTEGER NOT NULL,
    doc_type        TEXT    NOT NULL,
    doc_number      TEXT    NOT NULL,
    doc_date        TEXT    NOT NULL,
    payment_status  TEXT    NOT NULL DEFAULT 'Неплатена',
    -- Кога е платена. NULL = още не е платена.
    delivery_paid_date TEXT,
    -- Начин на плащане на доставката (Подход А). Различно от settlement_type на ред!
    payment_type    TEXT    NOT NULL DEFAULT 'Консигнация (отложено)',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

-- ============================================================
-- ТАБЛИЦА 4: РЕДОВЕ В ДОСТАВКАТА (Модул 3)
-- ============================================================
CREATE TABLE IF NOT EXISTS delivery_items (
    id              INTEGER PRIMARY KEY,
    delivery_id     INTEGER NOT NULL,
    product_id      INTEGER NOT NULL,
    quantity        INTEGER NOT NULL,
    settlement_type TEXT    NOT NULL,
    supplier_percent REAL   NOT NULL DEFAULT 0,
    -- Доставна цена в момента на доставката (историята помни цената ТОГАВА).
    delivery_price  REAL    NOT NULL DEFAULT 0,
    FOREIGN KEY (delivery_id) REFERENCES deliveries(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id)  REFERENCES products(id)
);

-- ============================================================
-- ТАБЛИЦА 5: ПРОДАЖБИ — "КАПАКЪТ" (Модули 4 и 5)
-- ВАЖНО: дефинираме я ПРЕДИ vouchers, защото vouchers сочат към sales.
-- ============================================================
CREATE TABLE IF NOT EXISTS sales (
    id              INTEGER PRIMARY KEY,
    order_number    TEXT,
    waybill_number  TEXT,
    status          TEXT    NOT NULL DEFAULT 'Чака плащане',
    payment_date    TEXT,
    payment_method  TEXT    NOT NULL DEFAULT 'Пощенски паричен превод',
    -- Допълнително плащане при ваучер с недостиг (Сценарий А).
    supplementary_payment_method TEXT,
    supplementary_amount REAL NOT NULL DEFAULT 0,
    -- Данни за фактура (NULL ако не е издадена)
    invoice_issued  INTEGER NOT NULL DEFAULT 0,
    invoice_number  TEXT,
    buyer_company   TEXT,
    buyer_eik       TEXT,
    buyer_mol       TEXT,
    buyer_address   TEXT,
    buyer_email     TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ============================================================
-- ТАБЛИЦА: ВАУЧЕРИ (Подаръчни ваучери с индивидуални кодове)
-- Дефинира се СЛЕД sales, защото има FK към нея.
-- ============================================================
CREATE TABLE IF NOT EXISTS vouchers (
    id              INTEGER PRIMARY KEY,
    code            TEXT    NOT NULL UNIQUE,
    nominal         REAL    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'Активен',
    valid_until     TEXT,
    issued_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    used_at         TEXT,
    issued_sale_id  INTEGER,
    used_sale_id    INTEGER,
    FOREIGN KEY (issued_sale_id) REFERENCES sales(id),
    FOREIGN KEY (used_sale_id) REFERENCES sales(id)
);

-- ============================================================
-- ТАБЛИЦА 6: РЕДОВЕ В ПРОДАЖБАТА
-- CHECK гарантира, че точно едно от двете (product_id/voucher_id) е попълнено.
-- ============================================================
CREATE TABLE IF NOT EXISTS sale_items (
    id              INTEGER PRIMARY KEY,
    sale_id         INTEGER NOT NULL,
    product_id      INTEGER,
    voucher_id      INTEGER,
    quantity        INTEGER NOT NULL,
    cost_price      REAL    NOT NULL DEFAULT 0,
    sale_price      REAL    NOT NULL DEFAULT 0,
    CHECK ((product_id IS NULL) != (voucher_id IS NULL)),
    FOREIGN KEY (sale_id)    REFERENCES sales(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (voucher_id) REFERENCES vouchers(id)
);

-- ============================================================
-- ТАБЛИЦА 7: КРЕДИТНИ ИЗВЕСТИЯ / СТОРНО (Модул 6)
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_notes (
    id              INTEGER PRIMARY KEY,
    sale_id         INTEGER NOT NULL,
    original_receipt TEXT   NOT NULL,
    returned_amount REAL    NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (sale_id) REFERENCES sales(id)
);

-- ============================================================
-- ТАБЛИЦА 8: ДВИЖЕНИЯ НА СКЛАДА — СЪРЦЕТО (Модул 7)
-- Текущата наличност = SUM(quantity_change) за даден product_id.
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_movements (
    id              INTEGER PRIMARY KEY,
    product_id      INTEGER NOT NULL,
    movement_type   TEXT    NOT NULL,
    quantity_change INTEGER NOT NULL,
    document_ref    TEXT,
    operator        TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (product_id) REFERENCES products(id)
);


-- ============================================================
-- ТАБЛИЦА: ОПЕРАТИВНИ РАЗХОДИ
-- Фирмени разходи извън доставките — наем, заплати, реклама, ток и т.н.
-- Филтрират се по date (дата на издаване), не по created_at (дата на въвеждане).
-- ============================================================
CREATE TABLE IF NOT EXISTS operating_expenses (
    id              INTEGER PRIMARY KEY,
    date            TEXT    NOT NULL,
    category        TEXT    NOT NULL,
    description     TEXT,
    amount          REAL    NOT NULL,
    document_number TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ============================================================
-- ИНДЕКСИ ЗА ПРОИЗВОДИТЕЛНОСТ
-- Наличността се смята като SUM(quantity_change) по product_id при ВСЯКО
-- зареждане на каталог/склад/продажба — без индекс това е пълно сканиране.
-- Останалите индекси покриват честите JOIN-ове по външни ключове в журналите.
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_stock_movements_product   ON stock_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_sale           ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_product        ON sale_items(product_id);
CREATE INDEX IF NOT EXISTS idx_delivery_items_delivery   ON delivery_items(delivery_id);
CREATE INDEX IF NOT EXISTS idx_delivery_items_product    ON delivery_items(product_id);
CREATE INDEX IF NOT EXISTS idx_sales_status              ON sales(status);
CREATE INDEX IF NOT EXISTS idx_deliveries_payment_status ON deliveries(payment_status);