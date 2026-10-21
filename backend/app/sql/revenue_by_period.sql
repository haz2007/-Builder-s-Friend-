-- Выручка без отмен по дням, неделям или месяцам — с пустыми периодами.
-- generate_series строит все корзины периода, LEFT JOIN оставляет нули там,
-- где заказов не было (иначе на графике «пропадали» бы дни).
-- :unit — 'day' | 'week' | 'month'; :period_start/:period_end — границы
-- (NULL — за всё время), :last_day — последний день периода.
WITH bounds AS (
    SELECT
        date_trunc(:unit, COALESCE(CAST(:period_start AS timestamp), MIN(created_at))) AS first_bucket,
        date_trunc(:unit, COALESCE(CAST(:last_day AS timestamp), MAX(created_at)))    AS last_bucket
    FROM orders
),
buckets AS (
    SELECT generate_series(first_bucket, last_bucket, CAST('1 ' || :unit AS interval)) AS bucket
    FROM bounds
    WHERE first_bucket IS NOT NULL
),
sales AS (
    SELECT date_trunc(:unit, created_at) AS bucket, total_price
    FROM orders
    WHERE status <> 'CANCELLED'
      AND (CAST(:period_start AS timestamp) IS NULL OR created_at >= :period_start)
      AND (CAST(:period_end AS timestamp) IS NULL OR created_at < :period_end)
)
SELECT
    b.bucket::date                                                        AS start,
    (b.bucket + CAST('1 ' || :unit AS interval) - interval '1 day')::date AS "end",
    COALESCE(SUM(s.total_price), 0)                                       AS revenue,
    COUNT(s.total_price)                                                  AS orders
FROM buckets AS b
LEFT JOIN sales AS s ON s.bucket = b.bucket
GROUP BY b.bucket
ORDER BY b.bucket;
