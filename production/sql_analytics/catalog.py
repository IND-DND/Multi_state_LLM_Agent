"""Versioned, reviewed semantic catalog; no live schema dump enters a prompt."""

VERSION = "2026-10-14.1"
SCHEMA = {
    "customers": {"customer_id": "INT", "tenant_id": "UUID", "region": "TEXT", "segment": "TEXT"},
    "products": {
        "product_id": "INT",
        "tenant_id": "UUID",
        "region": "TEXT",
        "product_name": "TEXT",
        "category": "TEXT",
    },
    "sales": {
        "sale_id": "INT",
        "tenant_id": "UUID",
        "region": "TEXT",
        "customer_id": "INT",
        "product_id": "INT",
        "sold_on": "DATE",
        "quantity": "INT",
        "net_amount": "DECIMAL",
        "status": "TEXT",
    },
}
RULES = """Revenue = SUM(sales.net_amount) WHERE sales.status = 'completed'.
All amounts are INR; sold_on is the business date in Asia/Kolkata.
sales grain is one sale line. net_amount is the total line amount, after discounts.
Never multiply net_amount by quantity. Refund/cancelled rows are excluded from revenue.
Join sales.customer_id = customers.customer_id AND sales.tenant_id = customers.tenant_id
AND sales.region = customers.region; equivalent keys for products.product_id.
No customer names, emails or other PII are exposed. Row access is enforced by the database.
Only schema-qualified analytics table names are supported. No CTEs, subqueries or unions.
Use explicit output aliases. Ask for clarification when a metric/date cannot be resolved.
"""


def catalog_for(datasets: list[str]) -> dict:
    return {
        "version": VERSION,
        "tables": {k: v for k, v in SCHEMA.items() if k in datasets},
        "rules": RULES,
    }
