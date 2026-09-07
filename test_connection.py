from utils.db_connection import execute_sql


query = """
SELECT
    p.product_name,
    c.customer_name,
    s.sale_date,
    s.quantity,
    s.revenue
FROM sales s
JOIN products p
    ON s.product_id = p.product_id
JOIN customers c
    ON s.customer_id = c.customer_id
ORDER BY s.sale_date;
"""


df = execute_sql(query)

print(df)