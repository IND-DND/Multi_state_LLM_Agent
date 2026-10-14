"""Administrator-only provisioning; no HTTP endpoint can grant access."""

import argparse
import hashlib
import os

import psycopg
from bootstrap import provision_scope

parser = argparse.ArgumentParser()
parser.add_argument("--identity-tenant", required=True)
parser.add_argument("--subject", required=True, help="Entra object ID (oid), not display name")
parser.add_argument("--business-tenant", required=True)
parser.add_argument("--regions", required=True, help="Comma-separated")
parser.add_argument("--datasets", default="sales,customers,products")
parser.add_argument("--permissions", default="analytics:query")
parser.add_argument("--disable", action="store_true")
args = parser.parse_args()
role = (
    "scope_" + hashlib.sha256((args.identity_tenant + ":" + args.subject).encode()).hexdigest()[:24]
)
with psycopg.connect(os.environ["MIGRATION_DSN"]) as conn:
    provision_scope(
        conn, role, args.business_tenant, args.regions.split(","), args.datasets.split(",")
    )
    conn.execute(
        """INSERT INTO control.principals(identity_tenant,subject,tenant_id,db_role,permissions,datasets,active)
        VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (identity_tenant,subject) DO UPDATE SET
        tenant_id=excluded.tenant_id,db_role=excluded.db_role,permissions=excluded.permissions,
        datasets=excluded.datasets,active=excluded.active,policy_version=control.principals.policy_version+1""",
        (
            args.identity_tenant,
            args.subject,
            args.business_tenant,
            role,
            args.permissions.split(","),
            args.datasets.split(","),
            not args.disable,
        ),
    )
print("Principal provisioned; previous snapshots require a new query.")
