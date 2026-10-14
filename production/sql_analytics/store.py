import hashlib
import json
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from .models import DomainError, Principal


class Store:
    def __init__(self, pool):
        self.pool = pool

    async def principal(self, tid: str, subject: str):
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                "SELECT identity_tenant,subject,tenant_id,db_role,permissions,datasets,policy_version FROM control.principals WHERE identity_tenant=%s AND subject=%s AND active",
                (tid, subject),
            )
            row = await cur.fetchone()
            return Principal(**row) if row else None

    async def rate_limit(self, p: Principal, maximum: int):
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """INSERT INTO control.rate_limits VALUES (%s,%s,date_trunc('minute',now()),1)
                ON CONFLICT (identity_tenant,subject,bucket) DO UPDATE SET count=control.rate_limits.count+1
                RETURNING count""",
                (p.identity_tenant, p.subject),
            )
            if (await cur.fetchone())["count"] > maximum:
                raise DomainError("rate_limit_exceeded", 429)

    async def create_run(self, p: Principal, key: UUID, question: str):
        async with self.pool.connection() as conn:
            await conn.execute(
                """INSERT INTO control.runs(id,identity_tenant,subject,idempotency_key,question,fingerprint)
                VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (uuid4(), p.identity_tenant, p.subject, key, question, p.fingerprint),
            )
            cur = await conn.execute(
                "SELECT * FROM control.runs WHERE identity_tenant=%s AND subject=%s AND idempotency_key=%s",
                (p.identity_tenant, p.subject, key),
            )
            run = await cur.fetchone()
        if run["question"] != question:
            raise DomainError("idempotency_key_reused", 409)
        self.check_fingerprint(run, p)
        return run

    @staticmethod
    def check_fingerprint(run, p):
        if run["fingerprint"] != p.fingerprint:
            raise DomainError("permissions_changed_submit_new_query", 409)

    async def owned_run(self, run_id: UUID, p: Principal):
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                "SELECT * FROM control.runs WHERE id=%s AND identity_tenant=%s AND subject=%s",
                (run_id, p.identity_tenant, p.subject),
            )
            row = await cur.fetchone()
        if not row:
            raise DomainError("run_not_found", 404)
        self.check_fingerprint(row, p)
        return row

    async def list_runs(self, p: Principal):
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                "SELECT id,question,status,created_at FROM control.runs "
                "WHERE identity_tenant=%s AND subject=%s AND fingerprint=%s "
                "ORDER BY created_at DESC LIMIT 20",
                (p.identity_tenant, p.subject, p.fingerprint),
            )
            return await cur.fetchall()

    @asynccontextmanager
    async def run_lock(self, run_id: UUID):
        # Session-scoped lock on a pinned connection: works across replicas and is
        # released by PostgreSQL when a crashed worker's connection disappears.
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                "SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS locked", (str(run_id),)
            )
            if not (await cur.fetchone())["locked"]:
                raise DomainError("run_in_progress", 409)
            try:
                yield
            finally:
                await conn.execute(
                    "SELECT pg_advisory_unlock(hashtextextended(%s,0))", (str(run_id),)
                )

    async def set_status(self, run_id, status, response=None, error=None):
        async with self.pool.connection() as conn:
            await conn.execute(
                "UPDATE control.runs SET status=%s,response=%s,error_code=%s,updated_at=now() WHERE id=%s",
                (status, Jsonb(response) if response is not None else None, error, run_id),
            )

    async def reserve_model_call(self, run_id, maximum):
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                "UPDATE control.runs SET model_calls=model_calls+1 WHERE id=%s AND model_calls < %s RETURNING model_calls",
                (run_id, maximum),
            )
            if await cur.fetchone() is None:
                raise DomainError("model_call_budget_exhausted", 422)

    async def result(self, run_id):
        async with self.pool.connection() as conn:
            cur = await conn.execute("SELECT * FROM control.results WHERE run_id=%s", (run_id,))
            return await cur.fetchone()

    async def save_result(self, run_id, query_hash, fingerprint, payload):
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        async with self.pool.connection() as conn:
            await conn.execute(
                "INSERT INTO control.results(run_id,query_hash,fingerprint,payload,digest) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (run_id, query_hash, fingerprint, Jsonb(payload), digest),
            )
        return await self.result(run_id)

    async def audit(self, subject, event, resource_id, outcome):
        async with self.pool.connection() as conn:
            await conn.execute(
                "INSERT INTO control.audit(subject,event,resource_id,outcome) VALUES (%s,%s,%s,%s)",
                (subject, event, str(resource_id), outcome),
            )

    async def request_export(self, run_id, p):
        run = await self.owned_run(run_id, p)
        if run["status"] != "completed":
            raise DomainError("run_not_completed", 409)
        result = await self.result(run_id)
        async with self.pool.connection() as conn:
            await conn.execute(
                "INSERT INTO control.approvals(id,run_id,tenant_id,digest,fingerprint) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (uuid4(), run_id, p.tenant_id, result["digest"], p.fingerprint),
            )
            cur = await conn.execute(
                "SELECT id,status,expires_at FROM control.approvals WHERE run_id=%s", (run_id,)
            )
            return await cur.fetchone()

    async def pending_approvals(self, p):
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """SELECT a.id,a.run_id,a.status,a.expires_at,r.subject AS requester
                FROM control.approvals a JOIN control.runs r ON r.id=a.run_id
                WHERE a.tenant_id=%s AND a.status='pending' AND a.expires_at>now()
                AND NOT (r.identity_tenant=%s AND r.subject=%s) ORDER BY a.created_at LIMIT 100""",
                (p.tenant_id, p.identity_tenant, p.subject),
            )
            return await cur.fetchall()

    async def decide(self, approval_id, p, approved):
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """UPDATE control.approvals a SET status=%s,reviewer=%s
                FROM control.runs r WHERE a.id=%s AND a.run_id=r.id AND a.tenant_id=%s
                AND a.status='pending' AND a.expires_at>now()
                AND NOT (r.identity_tenant=%s AND r.subject=%s) RETURNING a.id,a.status""",
                (
                    "approved" if approved else "denied",
                    p.identity_tenant + ":" + p.subject,
                    approval_id,
                    p.tenant_id,
                    p.identity_tenant,
                    p.subject,
                ),
            )
            row = await cur.fetchone()
        if not row:
            raise DomainError("approval_unavailable", 409)
        return row

    async def approved_result(self, run_id, p):
        await self.owned_run(run_id, p)
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """SELECT s.payload FROM control.results s JOIN control.approvals a USING(run_id)
                WHERE s.run_id=%s AND a.status='approved' AND a.expires_at>now()
                AND a.fingerprint=%s AND s.fingerprint=%s AND a.digest=s.digest""",
                (run_id, p.fingerprint, p.fingerprint),
            )
            row = await cur.fetchone()
        if not row:
            raise DomainError("export_approval_required", 403)
        return row["payload"]
