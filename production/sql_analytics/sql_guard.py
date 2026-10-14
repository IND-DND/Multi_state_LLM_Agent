"""Fail-closed SQL subset. SQLGlot is a parser, not the database security boundary."""

import hashlib
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify

from .catalog import SCHEMA
from .models import DomainError

# Every syntax node must be explicitly supported. This deliberately excludes CTEs,
# subqueries, set operations, windows, casts to custom types, and arbitrary functions.
ALLOWED_NODES = {
    "Select",
    "From",
    "Table",
    "Identifier",
    "Column",
    "Alias",
    "Literal",
    "Null",
    "Boolean",
    "Where",
    "And",
    "Or",
    "Not",
    "EQ",
    "NEQ",
    "GT",
    "GTE",
    "LT",
    "LTE",
    "Between",
    "In",
    "Is",
    "Like",
    "ILike",
    "Paren",
    "Join",
    "Group",
    "Order",
    "Ordered",
    "Limit",
    "Having",
    "Distinct",
    "Star",
    "Add",
    "Sub",
    "Mul",
    "Div",
    "Neg",
    "Sum",
    "Count",
    "Avg",
    "Min",
    "Max",
    "Round",
    "Coalesce",
    "Nullif",
    "DateTrunc",
    "TimestampTrunc",
    "Var",
    "TableAlias",
}
ALLOWED_FUNCTIONS = {
    "And",
    "Or",
    "Sum",
    "Count",
    "Avg",
    "Min",
    "Max",
    "Round",
    "Coalesce",
    "Nullif",
    "DateTrunc",
    "TimestampTrunc",
}


@dataclass(frozen=True)
class ValidatedQuery:
    sql: str
    digest: str


def validate_sql(raw: str, datasets: list[str], max_rows: int = 1000) -> ValidatedQuery:
    if len(raw) > 12000:
        raise DomainError("sql_too_large")
    try:
        statements = sqlglot.parse(raw, read="postgres")
    except sqlglot.errors.ParseError as exc:
        raise DomainError("sql_parse_error", 422) from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise DomainError("only_single_select_allowed")
    tree = statements[0]
    for node in tree.walk():
        name = type(node).__name__
        if name not in ALLOWED_NODES:
            raise DomainError("unsupported_sql_construct")
        if isinstance(node, exp.Func) and name not in ALLOWED_FUNCTIONS:
            raise DomainError("function_not_allowed")
        if isinstance(node, exp.Star) and not isinstance(node.parent, exp.Count):
            raise DomainError("explicit_columns_required")
        if isinstance(node, exp.Var) and node.name.upper() not in {
            "DAY",
            "WEEK",
            "MONTH",
            "QUARTER",
            "YEAR",
        }:
            raise DomainError("unsupported_date_unit")
    tables = list(tree.find_all(exp.Table))
    if not tables or len(tables) > 3:
        raise DomainError("invalid_table_count")
    for table in tables:
        if (
            table.catalog
            or table.db != "analytics"
            or table.name not in datasets
            or table.name not in SCHEMA
        ):
            raise DomainError("dataset_denied", 403)
        if any(table.args.get(k) for k in ("version", "sample", "pivots", "hints")):
            raise DomainError("unsupported_table_modifier")
    for join in tree.find_all(exp.Join):
        if join.args.get("on") is None or join.args.get("kind", "").upper() == "CROSS":
            raise DomainError("explicit_join_condition_required")
    try:
        tree = qualify(
            tree,
            dialect="postgres",
            schema={"analytics": {k: SCHEMA[k] for k in datasets if k in SCHEMA}},
            validate_qualify_columns=True,
            quote_identifiers=True,
        )
    except (sqlglot.errors.OptimizeError, sqlglot.errors.SchemaError) as exc:
        raise DomainError("unknown_or_ambiguous_column", 422) from exc
    # Duplicate output names otherwise silently overwrite dict-row values.
    names = tree.named_selects
    if len(names) != len(set(names)):
        raise DomainError("duplicate_output_columns", 422)
    limit = tree.args.get("limit")
    if limit:
        expression = limit.expression
        if not isinstance(expression, exp.Literal) or not expression.is_int:
            raise DomainError("invalid_limit")
        if int(expression.this) < 1:
            raise DomainError("invalid_limit")
        row_limit = min(int(expression.this), max_rows + 1)
    else:
        row_limit = max_rows + 1
    tree = tree.limit(row_limit)
    sql = tree.sql(dialect="postgres")
    return ValidatedQuery(sql, hashlib.sha256(sql.encode()).hexdigest())
