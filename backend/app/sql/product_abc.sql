-- ABC-анализ товаров по выручке за период.
-- A — товары, которые вместе дают первые 80 % выручки, B — следующие 15 %,
-- C — остальные 5 %. Оконные функции считают по уже сгруппированным продажам:
--   RANK()                       — место товара по выручке;
--   SUM() OVER ()                — вся выручка периода (знаменатель доли);
--   SUM() OVER (ORDER BY …)      — накопленная выручка «до этого товара включительно».
WITH sales AS (
    SELECT
        p.id   AS product_id,
        p.name AS name,
        SUM(oi.quantity * oi.base_quantity) AS base_quantity_sold,
        p.unit                              AS unit,
        SUM(oi.price * oi.quantity)         AS revenue
    FROM order_items AS oi
    JOIN orders   AS o ON o.id = oi.order_id
    JOIN products AS p ON p.id = oi.product_id
    WHERE o.status <> 'CANCELLED'
      AND (CAST(:period_start AS timestamp) IS NULL OR o.created_at >= :period_start)
      AND (CAST(:period_end AS timestamp) IS NULL OR o.created_at < :period_end)
    GROUP BY p.id, p.name, p.unit
),
ranked AS (
    SELECT
        *,
        RANK() OVER (ORDER BY revenue DESC)    AS rank,
        revenue / SUM(revenue) OVER ()         AS share,
        SUM(revenue) OVER (ORDER BY revenue DESC, product_id ROWS UNBOUNDED PRECEDING)
            / SUM(revenue) OVER ()             AS cumulative_share
    FROM sales
)
SELECT
    product_id,
    name,
    base_quantity_sold,
    unit,
    revenue,
    rank,
    ROUND(share * 100, 1)            AS share_pct,
    ROUND(cumulative_share * 100, 1) AS cumulative_pct,
    -- класс по накопленной доле ДО товара: первый товар всегда A
    CASE
        WHEN cumulative_share - share < 0.80 THEN 'A'
        WHEN cumulative_share - share < 0.95 THEN 'B'
        ELSE 'C'
    END AS abc_class
FROM ranked
ORDER BY rank, product_id;
