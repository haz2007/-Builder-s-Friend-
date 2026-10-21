# SQL: отчёты, индексы, типы данных

Аналитика админки считается в PostgreSQL, а не в Python: запросы лежат в
[`backend/app/sql/`](../../backend/app/sql) отдельными файлами, их выполняет
[`services/reports.py`](../../backend/app/services/reports.py). API — `GET /api/v1/admin/analytics`
и `GET /api/v1/admin/reports`, проверки на данных с известным ответом —
[`tests/test_sql_reports.py`](../../tests/test_sql_reports.py).

## Отчёты

| Файл | Что считает | Приёмы |
|---|---|---|
| [`revenue_by_period.sql`](../../backend/app/sql/revenue_by_period.sql) | Выручка по дням / неделям / месяцам для графика — **с пустыми периодами** | CTE, `generate_series`, `date_trunc`, `LEFT JOIN` к сетке периодов |
| [`category_revenue.sql`](../../backend/app/sql/category_revenue.sql) | Выручка по разделам: подкатегории любой глубины сворачиваются в корень (Обрезная доска → Доска → Пиломатериалы) | **Рекурсивный CTE** по `parent_id` |
| [`product_abc.sql`](../../backend/app/sql/product_abc.sql) | **ABC-анализ**: A — товары, дающие первые 80 % выручки, B — следующие 15 %, C — остальное | Оконные функции: `RANK()`, `SUM() OVER ()`, накопительная `SUM() OVER (ORDER BY … ROWS UNBOUNDED PRECEDING)` |
| [`monthly_summary.sql`](../../backend/app/sql/monthly_summary.sql) | По месяцам за год: заказы, выручка, средний чек, доля самовывоза, **рост к прошлому месяцу** | `LAG()` с именованным окном `WINDOW w`, агрегат с `FILTER (WHERE …)`, `NULLIF` от деления на ноль |
| [`repeat_customers.sql`](../../backend/app/sql/repeat_customers.sql) | Сколько покупателей вернулись и через сколько дней в среднем | `ROW_NUMBER()` и `LAG()` с `PARTITION BY user_id` |

Пример — ABC-анализ: класс определяется по накопленной доле **до** товара,
поэтому самый продаваемый товар всегда попадает в A, даже если один даёт 90 %:

```sql
SUM(revenue) OVER (ORDER BY revenue DESC, product_id ROWS UNBOUNDED PRECEDING)
    / SUM(revenue) OVER ()                     AS cumulative_share
...
CASE
    WHEN cumulative_share - share < 0.80 THEN 'A'
    WHEN cumulative_share - share < 0.95 THEN 'B'
    ELSE 'C'
END AS abc_class
```

## Индексы — замер «до и после»

PostgreSQL сам индексирует только первичные ключи и UNIQUE, а внешние ключи — нет.
Индексы подобраны под реальные запросы приложения (миграция
[`c5d7e9f1a3b4`](../../backend/alembic/versions/c5d7e9f1a3b4_add_query_indexes.py)).

Замер — [`backend/benchmarks/index_benchmark.py`](../../backend/benchmarks/index_benchmark.py):
создаёт отдельную базу, заполняет её 200 000 заказов (600 000 позиций, 600 000 записей
истории, 200 000 уведомлений, 20 000 покупателей), выполняет `EXPLAIN ANALYZE` каждого
запроса 7 раз без индексов и с ними и берёт медиану. PostgreSQL 15, ноутбук на Apple Silicon.

| Запрос | Без индексов | С индексами | Ускорение | План без индексов → с индексами |
|---|---:|---:|---:|---|
| Мои заказы покупателя | 42.49 мс | 0.02 мс | ×2656 | Index Scan `orders_pkey` → Index Scan `ix_orders_user_id_id` |
| Позиции заказа | 8.95 мс | 0.01 мс | ×994 | Seq Scan → Bitmap Index Scan `ix_order_items_order_id` |
| История статусов заказа | 8.02 мс | 0.01 мс | ×535 | Seq Scan → Bitmap Index Scan `ix_order_status_history_order_id` |
| Непрочитанные уведомления | 5.06 мс | 0.01 мс | ×506 | Seq Scan → Bitmap Index Scan `ix_notifications_user_id_is_read` |
| Счётчик новых заказов | 4.42 мс | 0.54 мс | ×8 | Seq Scan → Bitmap Index Scan `ix_orders_status_created_at` |
| Выручка по дням за 30 дней | 6.64 мс | 3.56 мс | ×2 | Seq Scan → Bitmap Index Scan `ix_orders_created_at` |
| ABC-анализ за 30 дней | 31.07 мс | 26.86 мс | ×1 | позиции — всё равно Seq Scan (см. ниже) |

Что видно из замера:

- **«Мои заказы»** — запрос `WHERE user_id = … ORDER BY id DESC LIMIT 20`. Индекс только
  по `user_id` планировщик **не выбрал**: ему выгоднее идти по первичному ключу с конца
  и отбрасывать чужие заказы. Помог составной индекс `(user_id, id)` — он сразу отдаёт
  последние заказы покупателя в нужном порядке.
- **По внешним ключам** (позиции, история, уведомления) — ускорение в сотни раз: вместо
  чтения всей таблицы читаются несколько строк.
- **ABC-анализ** почти не ускорился, и это правильно: за 30 дней в отчёт попадает ~10 %
  всех позиций, и одно последовательное чтение таблицы с хеш-соединением дешевле десятков
  тысяч обращений по индексу. Индекс по дате помог только отобрать заказы периода.

## Поиск с опечатками — pg_trgm

Обычный поиск по словам (`ILIKE`) не находит «досака». Тогда запрос сравнивается с
названиями по триграммам: `word_similarity` ищет в названии место, больше всего похожее на
запрос, а оператор `%>` с порогом `0,35` (только для этой транзакции, `SET LOCAL`) идёт по
GIN-индексу.

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX ix_products_name_trgm ON products USING gin (lower(name) gin_trgm_ops);

SET LOCAL pg_trgm.word_similarity_threshold = 0.35;
SELECT id, name, word_similarity('досака', lower(name)) AS score
FROM products
WHERE lower(name) %> 'досака' AND is_active = 1
ORDER BY score DESC
LIMIT 5;
```

```
Bitmap Heap Scan on products
  Recheck Cond: (lower((name)::text) %> 'досака'::text)
  ->  Bitmap Index Scan on ix_products_name_trgm
        Index Cond: (lower((name)::text) %> 'досака'::text)
```

Код — `backend/app/services/search.py`, тест плана запроса — `tests/test_fuzzy_search.py`.

## Деньги — NUMERIC, а не float

`float` хранит десятичные дроби приближённо: `1.10 * 3 = 3.3000000000000003`.
Цены и суммы хранятся как `NUMERIC(12, 2)`, остатки и количества — `NUMERIC(12, 3)`
(крепёж продаётся на вес). Миграция
[`a3b5c7d9e1f2`](../../backend/alembic/versions/a3b5c7d9e1f2_money_and_quantities_as_numeric.py)
переводит столбцы с `round(…)`; проверка — `test_money_is_exact_numeric`.

В Python значения читаются как `float` (`Numeric(asdecimal=False)`): расчёты в коде
простые, а точное хранение и округление до копеек обеспечивает база.

## Дата заказа — в самом заказе

Раньше дата заказа каждый раз вычислялась как `MIN(created_at)` по истории статусов —
подзапрос с `GROUP BY` в каждом отчёте, и по нему нельзя построить индекс. Миграция
[`b4c6d8e0f2a3`](../../backend/alembic/versions/b4c6d8e0f2a3_add_orders_created_at.py)
добавила `orders.created_at` и заполнила его для старых заказов из истории одним `UPDATE … FROM`.
