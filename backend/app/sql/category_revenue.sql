-- Выручка по разделам каталога: подкатегории любой глубины сворачиваются
-- в свой корневой раздел (Доска, Брус → Пиломатериалы).
-- Рекурсивный CTE поднимается по parent_id от каждой категории к корню.
WITH RECURSIVE category_root AS (
    SELECT id, id AS root_id
    FROM categories
    WHERE parent_id IS NULL
  UNION ALL
    SELECT child.id, parent.root_id
    FROM categories AS child
    JOIN category_root AS parent ON child.parent_id = parent.id
),
sales AS (
    SELECT p.category_id, SUM(oi.price * oi.quantity) AS revenue
    FROM order_items AS oi
    JOIN orders   AS o ON o.id = oi.order_id
    JOIN products AS p ON p.id = oi.product_id
    WHERE o.status <> 'CANCELLED'
      AND (CAST(:period_start AS timestamp) IS NULL OR o.created_at >= :period_start)
      AND (CAST(:period_end AS timestamp) IS NULL OR o.created_at < :period_end)
    GROUP BY p.category_id
)
SELECT COALESCE(root.name, 'Без раздела') AS name, SUM(s.revenue) AS revenue
FROM sales AS s
LEFT JOIN category_root AS cr   ON cr.id = s.category_id
LEFT JOIN categories    AS root ON root.id = cr.root_id
GROUP BY COALESCE(root.name, 'Без раздела')
ORDER BY revenue DESC;
