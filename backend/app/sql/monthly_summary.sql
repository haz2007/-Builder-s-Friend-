-- Сводка по месяцам за последний год: заказы, выручка, средний чек,
-- доля самовывоза и рост выручки к прошлому месяцу.
-- FILTER считает самовывоз в том же проходе, LAG() берёт прошлый месяц.
WITH monthly AS (
    SELECT
        date_trunc('month', created_at)                        AS month,
        COUNT(*)                                               AS orders,
        SUM(total_price)                                       AS revenue,
        AVG(total_price)                                       AS average_check,
        COUNT(*) FILTER (WHERE delivery_method = 'PICKUP')     AS pickup_orders
    FROM orders
    WHERE status <> 'CANCELLED'
      AND created_at >= date_trunc('month', CAST(:today AS timestamp)) - interval '11 months'
    GROUP BY date_trunc('month', created_at)
)
SELECT
    month::date                                    AS month,
    orders,
    revenue,
    ROUND(average_check, 2)                        AS average_check,
    ROUND(100.0 * pickup_orders / orders, 1)       AS pickup_pct,
    ROUND(
        100.0 * (revenue - LAG(revenue) OVER w) / NULLIF(LAG(revenue) OVER w, 0),
        1
    )                                              AS revenue_change_pct
FROM monthly
WINDOW w AS (ORDER BY month)
ORDER BY month;
