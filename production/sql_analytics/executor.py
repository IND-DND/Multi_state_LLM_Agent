import datetime
import decimal
import json
from uuid import UUID

from psycopg import sql

from .models import DomainError
from .sql_guard import validate_sql


def json_value(value):
    if isinstance(value, decimal.Decimal):
        return str(value)  # Preserve financial precision; UI explicitly converts for plotting.
    if isinstance(value, (datetime.date, datetime.datetime, UUID)):
        return str(value)
    return value


class QueryExecutor:
    def __init__(self, pool, settings):
        self.pool, self.settings = pool, settings

    async def execute(self, raw: str, principal):
        s = self.settings
        query = validate_sql(raw, principal.datasets, s.max_rows)
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute("SET TRANSACTION READ ONLY")
                # Only the backend chooses this role from the provisioned entitlement.
                await conn.execute(
                    sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(principal.db_role))
                )
                await conn.execute(
                    "SELECT set_config('statement_timeout',%s,true)", (str(s.statement_timeout_ms),)
                )
                await conn.execute("SET LOCAL lock_timeout='1s'")
                await conn.execute("SET LOCAL search_path=pg_catalog,analytics")
                cur = await conn.execute(query.sql)
                columns = [column.name for column in cur.description]
                records = await cur.fetchmany(s.max_rows + 1)
        truncated = len(records) > s.max_rows
        payload = {
            "columns": columns,
            "rows": [{k: json_value(v) for k, v in row.items()} for row in records[: s.max_rows]],
            "truncated": truncated,
        }
        if len(json.dumps(payload).encode()) > s.max_result_bytes:
            raise DomainError("result_too_large_refine_query", 422)
        return query, payload
