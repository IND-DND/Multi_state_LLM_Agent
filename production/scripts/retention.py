"""Explicit administrator maintenance command; does not run automatically."""

import argparse
import asyncio
import os

import psycopg
from dotenv import load_dotenv
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

load_dotenv()
parser = argparse.ArgumentParser()
parser.add_argument("--days", type=int, required=True)
args = parser.parse_args()
if args.days < 1:
    raise SystemExit("Retention must be at least one day")


async def main():
    async with await psycopg.AsyncConnection.connect(
        os.environ["MIGRATION_DSN"], autocommit=True
    ) as conn:
        cur = await conn.execute(
            "SELECT id FROM control.runs WHERE updated_at < now() - %s * interval '1 day'",
            (args.days,),
        )
        runs = await cur.fetchall()
        async with AsyncPostgresSaver.from_conn_string(os.environ["CHECKPOINT_DSN"]) as saver:
            for (run_id,) in runs:
                lock = await conn.execute(
                    "SELECT pg_try_advisory_lock(hashtextextended(%s,0))", (str(run_id),)
                )
                if not (await lock.fetchone())[0]:
                    continue
                try:
                    # Recheck after acquiring the same lock used by the API.
                    current = await conn.execute(
                        "SELECT 1 FROM control.runs WHERE id=%s AND updated_at < now() - %s * interval '1 day'",
                        (run_id, args.days),
                    )
                    if await current.fetchone():
                        await saver.adelete_thread(str(run_id))
                        await conn.execute("DELETE FROM control.runs WHERE id=%s", (run_id,))
                finally:
                    await conn.execute(
                        "SELECT pg_advisory_unlock(hashtextextended(%s,0))", (str(run_id),)
                    )
        await conn.execute(
            "DELETE FROM control.rate_limits WHERE bucket < now() - interval '2 days'"
        )
    print("Retention maintenance completed; audit records were preserved.")


asyncio.run(main())
