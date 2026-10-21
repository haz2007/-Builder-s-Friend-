"""Замер индексов: время запросов приложения без индексов и с ними.

Создаёт отдельную базу wood_commerce_bench (рабочую не трогает), заполняет
её 200 000 заказов, запускает EXPLAIN ANALYZE до и после создания индексов
из миграции c5d7e9f1a3b4 и печатает таблицу для docs/sql/README.md.
В конце база удаляется.

    cd backend && .venv/bin/python benchmarks/index_benchmark.py
"""

import json
import os
import statistics
import sys
from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5110/wood_commerce")

from app import models  # noqa: E402,F401 — регистрирует таблицы
from app.database import Base  # noqa: E402
from app.services.reports import load_sql  # noqa: E402

BENCH_DB = "wood_commerce_bench"
RUNS = 7

# Индексы из миграции c5d7e9f1a3b4 — их и сравниваем
INDEXES = [
    ("ix_orders_user_id_id", "orders", "user_id, id"),
    ("ix_orders_created_at", "orders", "created_at"),
    ("ix_orders_status_created_at", "orders", "status, created_at"),
    ("ix_order_items_order_id", "order_items", "order_id"),
    ("ix_order_items_product_id", "order_items", "product_id"),
    ("ix_order_status_history_order_id", "order_status_history", "order_id"),
    ("ix_notifications_user_id_is_read", "notifications", "user_id, is_read"),
    ("ix_products_category_id", "products", "category_id"),
    ("ix_product_categories_category_id", "product_categories", "category_id"),
]

FILL = """
INSERT INTO categories (name) SELECT 'Раздел ' || g FROM generate_series(1, 10) AS g;

INSERT INTO products (name, price, stock_quantity, unit, category_id, is_active)
SELECT 'Товар ' || g, round((100 + random() * 2000)::numeric, 2), 100000, 'шт', 1 + g % 10, 1
FROM generate_series(1, 300) AS g;

INSERT INTO product_variants (product_id, name, unit, price, base_quantity, is_active)
SELECT id, 'Штука', 'шт', price, 1, 1 FROM products;

INSERT INTO users (phone, password_hash, role)
SELECT '+7900' || lpad(g::text, 7, '0'), 'x', 'CUSTOMER' FROM generate_series(1, 20000) AS g;

-- 200 000 заказов за два года; новых — около 1 %, как в живом магазине
INSERT INTO orders (status, total_price, delivery_address, delivery_method, customer_name, user_id, created_at)
SELECT
    CASE WHEN r < 0.01 THEN 'NEW' WHEN r < 0.03 THEN 'PREPARING' WHEN r < 0.10 THEN 'CANCELLED' ELSE 'DELIVERED' END,
    0, 'Химки', CASE WHEN random() < 0.3 THEN 'PICKUP' ELSE 'DELIVERY' END, 'Покупатель',
    1 + (random() * 19999)::int,
    (now() AT TIME ZONE 'UTC') - random() * interval '730 days'
FROM (SELECT random() AS r FROM generate_series(1, 200000)) AS s;

INSERT INTO order_items (order_id, product_id, variant_id, quantity, price, unit, base_quantity)
SELECT o.id, v.product_id, v.id, 1 + (random() * 20)::int, v.price, 'шт', 1
FROM orders AS o
CROSS JOIN generate_series(1, 3) AS n
CROSS JOIN LATERAL (
    SELECT * FROM product_variants
    WHERE id = 1 + ((o.id * 7919 + n * 104729) % 300)
) AS v;

UPDATE orders AS o SET total_price = s.total
FROM (SELECT order_id, SUM(price * quantity) AS total FROM order_items GROUP BY order_id) AS s
WHERE s.order_id = o.id;

INSERT INTO order_status_history (order_id, status, created_at)
SELECT o.id, step.status, o.created_at + step.n * interval '1 hour'
FROM orders AS o
CROSS JOIN (VALUES (0, 'NEW'), (1, 'CONFIRMED'), (2, 'PREPARING')) AS step (n, status);

INSERT INTO notifications (user_id, order_id, status, message, is_read, created_at)
SELECT o.user_id, o.id, 'CONFIRMED', 'Ваш заказ подтверждён.', (random() < 0.9)::int, o.created_at
FROM orders AS o;
"""

QUERIES = [
    ("Мои заказы покупателя",
     "SELECT id, status, total_price, created_at FROM orders WHERE user_id = :user_id ORDER BY id DESC LIMIT 20",
     {"user_id": 4242}),
    ("Позиции заказа",
     "SELECT * FROM order_items WHERE order_id = :order_id",
     {"order_id": 123456}),
    ("История статусов заказа",
     "SELECT * FROM order_status_history WHERE order_id = :order_id ORDER BY id",
     {"order_id": 123456}),
    ("Непрочитанные уведомления",
     "SELECT count(*) FROM notifications WHERE user_id = :user_id AND is_read = 0",
     {"user_id": 4242}),
    ("Счётчик новых заказов",
     "SELECT count(*) FROM orders WHERE status = 'NEW'",
     {}),
]


def explain(conn, sql: str, params: dict) -> tuple[float, str]:
    times, node = [], ""
    for _ in range(RUNS):
        plan = conn.execute(text("EXPLAIN (ANALYZE, FORMAT JSON) " + sql), params).scalar()
        if isinstance(plan, str):
            plan = json.loads(plan)
        times.append(plan[0]["Execution Time"])
        node = scan_nodes(plan[0]["Plan"])
    return statistics.median(times), node


def scan_nodes(plan: dict) -> str:
    """Какими способами PostgreSQL читал таблицы: Seq Scan / Index Scan …"""
    found = []

    def walk(node):
        if "Index Name" in node or ("Scan" in node["Node Type"] and "Relation Name" in node):
            index = node.get("Index Name")
            found.append(f'{node["Node Type"]} {index or node["Relation Name"]}')
        for child in node.get("Plans", []):
            walk(child)

    walk(plan)
    return ", ".join(dict.fromkeys(found)) or plan["Node Type"]


def main():
    url = make_url(os.environ["DATABASE_URL"])
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {BENCH_DB}"))
        conn.execute(text(f"CREATE DATABASE {BENCH_DB}"))

    engine = create_engine(url.set(database=BENCH_DB))
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            for name, _, _ in INDEXES:
                conn.execute(text(f"DROP INDEX IF EXISTS {name}"))
            print("Заполняю базу…", flush=True)
            # Напрямую через psycopg: без параметров «%» в SQL не считается меткой
            conn.connection.dbapi_connection.execute(FILL)
        with engine.connect() as conn:
            conn.execute(text("ANALYZE"))
            counts = {
                table: conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()
                for table in ("orders", "order_items", "order_status_history", "notifications", "users")
            }
            end = conn.execute(text("SELECT date_trunc('day', now() AT TIME ZONE 'UTC') + interval '1 day'")).scalar()

        period = {"period_start": end - timedelta(days=30), "period_end": end}
        queries = QUERIES + [
            ("Выручка по дням за 30 дней (revenue_by_period.sql)",
             load_sql("revenue_by_period").text,
             {**period, "unit": "day", "last_day": end - timedelta(days=1)}),
            ("ABC-анализ за 30 дней (product_abc.sql)",
             load_sql("product_abc").text,
             period),
        ]

        results = {}
        for stage in ("before", "after"):
            if stage == "after":
                with engine.begin() as conn:
                    for name, table, columns in INDEXES:
                        conn.execute(text(f"CREATE INDEX {name} ON {table} ({columns})"))
                with engine.connect() as conn:
                    conn.execute(text("ANALYZE"))
            with engine.connect() as conn:
                for title, sql, params in queries:
                    results.setdefault(title, {})[stage] = explain(conn, sql, params)

        print()
        print("Данные: " + ", ".join(f"{table} — {count:,}".replace(",", " ") for table, count in counts.items()))
        print()
        print("| Запрос | Без индексов | С индексами | Ускорение | План без индексов → с индексами |")
        print("|---|---:|---:|---:|---|")
        for title, stages in results.items():
            before, node_before = stages["before"]
            after, node_after = stages["after"]
            print(
                f"| {title} | {before:.2f} мс | {after:.2f} мс | ×{before / after:.0f} "
                f"| {node_before} → {node_after} |"
            )
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {BENCH_DB}"))


if __name__ == "__main__":
    main()
