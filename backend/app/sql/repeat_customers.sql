-- Повторные покупки: сколько покупателей вернулись и через сколько дней
-- в среднем делают следующий заказ.
-- ROW_NUMBER() и LAG() с PARTITION BY user_id нумеруют заказы каждого
-- покупателя и находят разрыв с его предыдущим заказом.
WITH customer_orders AS (
    SELECT
        user_id,
        ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at, id) AS order_number,
        created_at - LAG(created_at) OVER (PARTITION BY user_id ORDER BY created_at, id) AS gap
    FROM orders
    WHERE status <> 'CANCELLED'
)
SELECT
    COUNT(DISTINCT user_id)                                     AS customers,
    COUNT(DISTINCT user_id) FILTER (WHERE order_number = 2)     AS repeat_customers,
    ROUND(CAST(EXTRACT(EPOCH FROM AVG(gap)) / 86400 AS numeric), 1) AS average_days_between_orders
FROM customer_orders;
