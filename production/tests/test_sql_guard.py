import pytest

from sql_analytics.models import DomainError
from sql_analytics.sql_guard import validate_sql


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM analytics.sales",
        "SELECT sale_id FROM analytics.sales; DELETE FROM analytics.sales",
        "WITH x AS (DELETE FROM analytics.sales RETURNING *) SELECT * FROM x",
        "SELECT pg_sleep(5) FROM analytics.sales",
        "SELECT set_config('role','postgres',true) FROM analytics.sales",
        "SELECT pg_read_file('/etc/passwd') FROM analytics.sales",
        "SELECT dblink('host=evil', 'select 1') FROM analytics.sales",
        "SELECT lo_export(1, '/tmp/x') FROM analytics.sales",
        "SELECT * FROM analytics.sales",
        "SELECT sale_id INTO backup FROM analytics.sales",
        "SELECT sale_id FROM analytics.sales FOR UPDATE",
        "SELECT sale_id FROM analytics.sales UNION SELECT oid FROM pg_roles",
        "SELECT oid FROM pg_catalog.pg_roles",
        "SELECT sale_id FROM other.sales",
        "SELECT sale_id FROM analytics.sales OFFSET 100",
        "SELECT sale_id::regclass FROM analytics.sales",
        "SELECT (SELECT secret FROM control.runs) FROM analytics.sales",
        "SELECT s.sale_id FROM analytics.sales s CROSS JOIN analytics.products p",
        "SELECT public.evil(net_amount) FROM analytics.sales",
        "SELECT sale_id FROM analytics.sales LIMIT -1",
        "SELECT customer_email FROM analytics.customers",
        "SELECT s.sale_id AS x, s.quantity AS x FROM analytics.sales s",
        "SELECT sale_id FROM analytics.sales TABLESAMPLE SYSTEM(10)",
    ],
)
def test_rejects_unsafe_or_unsupported_sql(query):
    with pytest.raises(DomainError):
        validate_sql(query, ["sales", "products", "customers"])


def test_table_permission_is_enforced():
    with pytest.raises(DomainError, match="dataset_denied"):
        validate_sql("SELECT product_id FROM analytics.products", ["sales"])


@pytest.mark.parametrize(
    "query",
    [
        "SELECT SUM(net_amount) AS revenue FROM analytics.sales WHERE status='completed'",
        "SELECT DATE_TRUNC('month', sold_on) AS month, SUM(net_amount) AS revenue FROM analytics.sales GROUP BY DATE_TRUNC('month', sold_on) ORDER BY month",
        "SELECT p.category, SUM(s.net_amount) AS revenue FROM analytics.sales s JOIN analytics.products p ON s.product_id=p.product_id AND s.tenant_id=p.tenant_id AND s.region=p.region GROUP BY p.category",
        "SELECT COUNT(DISTINCT customer_id) AS customers FROM analytics.sales",
        "SELECT COUNT(*) AS count FROM analytics.sales",
    ],
)
def test_supported_queries_and_stable_revalidation(query):
    first = validate_sql(query, ["sales", "products"])
    assert "LIMIT 1001" in first.sql
    assert validate_sql(first.sql, ["sales", "products"]).digest == first.digest


def test_limits_capped_and_small_limits_preserved():
    assert (
        "LIMIT 11"
        in validate_sql("SELECT sale_id FROM analytics.sales LIMIT 999999", ["sales"], 10).sql
    )
    assert (
        "LIMIT 3" in validate_sql("SELECT sale_id FROM analytics.sales LIMIT 3", ["sales"], 10).sql
    )
