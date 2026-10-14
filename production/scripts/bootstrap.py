"""Provision a dedicated database. Supply administrator credentials only to this job."""

import argparse
import asyncio
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import sql

load_dotenv()
ROOT = Path(__file__).resolve().parents[1]


def provision_scope(conn, role, tenant, regions, datasets):
    if not role.startswith("scope_"):
        raise ValueError("Data roles must start with scope_")
    if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
        conn.execute(
            sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOBYPASSRLS").format(sql.Identifier(role))
        )
    conn.execute(sql.SQL("GRANT {} TO analytics_gateway").format(sql.Identifier(role)))
    conn.execute(
        sql.SQL("GRANT USAGE ON SCHEMA analytics,app_private TO {}").format(sql.Identifier(role))
    )
    conn.execute(
        sql.SQL("GRANT EXECUTE ON FUNCTION app_private.can_read(name,uuid,text) TO {}").format(
            sql.Identifier(role)
        )
    )
    conn.execute(
        sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA analytics FROM {}").format(sql.Identifier(role))
    )
    for dataset in datasets:
        if dataset not in {"sales", "customers", "products"}:
            raise ValueError("Unknown dataset")
        conn.execute(
            sql.SQL("GRANT SELECT ON analytics.{} TO {}").format(
                sql.Identifier(dataset), sql.Identifier(role)
            )
        )
    conn.execute("DELETE FROM app_private.role_scopes WHERE db_role=%s", (role,))
    for region in regions:
        conn.execute(
            "INSERT INTO app_private.role_scopes VALUES (%s,%s,%s)", (role, tenant, region)
        )
    # Invalidate all cached result authorizations when a shared scope changes.
    conn.execute(
        "UPDATE control.principals SET policy_version=policy_version+1 WHERE db_role=%s", (role,)
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--demo", action="store_true", help="Install synthetic data and local demo principals"
    )
    args = parser.parse_args()
    if args.demo and os.getenv("ENVIRONMENT") == "production":
        raise SystemExit("Refusing demo seed in production")
    with psycopg.connect(os.environ["MIGRATION_DSN"], autocommit=True) as conn:
        for role, env_key in [
            ("analytics_gateway", "QUERY_DB_PASSWORD"),
            ("analytics_control", "CONTROL_DB_PASSWORD"),
            ("analytics_checkpoint", "CHECKPOINT_DB_PASSWORD"),
        ]:
            password = os.environ[env_key]
            if len(password) < 24:
                raise ValueError("Database passwords must be at least 24 characters")
            if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
                conn.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD {}"
                    ).format(sql.Identifier(role), sql.Literal(password))
                )
        conn.execute((ROOT / "sql/001_schema.sql").read_text())
        conn.execute("CREATE SCHEMA IF NOT EXISTS checkpoints AUTHORIZATION analytics_checkpoint")
        conn.execute("ALTER ROLE analytics_checkpoint SET search_path=checkpoints")
        conn.execute("ALTER ROLE analytics_gateway SET default_transaction_read_only=on")
        conn.execute("GRANT USAGE ON SCHEMA control TO analytics_control")
        conn.execute("GRANT SELECT ON control.principals TO analytics_control")
        conn.execute(
            "GRANT SELECT,INSERT,UPDATE ON control.runs,control.results,control.approvals,control.rate_limits TO analytics_control"
        )
        conn.execute("GRANT INSERT ON control.audit TO analytics_control")
        conn.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA control TO analytics_control")
        if args.demo:
            conn.execute((ROOT / "sql/002_demo.sql").read_text())
            tenant_a = "11111111-1111-1111-1111-111111111111"
            tenant_b = "22222222-2222-2222-2222-222222222222"
            examples = [
                ("analyst-north", tenant_a, ["north"], ["analytics:query", "analytics:export"]),
                (
                    "manager",
                    tenant_a,
                    ["north", "south"],
                    [
                        "analytics:query",
                        "analytics:export",
                        "approvals:review",
                        "operations:metrics",
                    ],
                ),
                (
                    "other-tenant",
                    tenant_b,
                    ["north"],
                    ["analytics:query", "analytics:export", "approvals:review"],
                ),
                ("viewer", tenant_a, ["north"], ["analytics:query"]),
            ]
            for subject, tenant, regions, permissions in examples:
                role = "scope_" + subject.replace("-", "_")
                datasets = ["sales", "customers", "products"]
                provision_scope(conn, role, tenant, regions, datasets)
                conn.execute(
                    """INSERT INTO control.principals(identity_tenant,subject,tenant_id,db_role,permissions,datasets)
                    VALUES ('demo',%s,%s,%s,%s,%s) ON CONFLICT (identity_tenant,subject) DO NOTHING""",
                    (subject, tenant, role, permissions, datasets),
                )

    async def checkpoints():
        async with AsyncPostgresSaver.from_conn_string(os.environ["CHECKPOINT_DSN"]) as saver:
            await saver.setup()

    asyncio.run(checkpoints())
    print("Database schema and workflow checkpoints are ready.")


if __name__ == "__main__":
    main()
