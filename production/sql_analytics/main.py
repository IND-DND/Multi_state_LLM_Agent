import asyncio
import csv
import io
import logging
import time
from contextlib import AsyncExitStack, asynccontextmanager
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from psycopg import Error as DatabaseError
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .auth import TokenVerifier, require
from .config import get_settings
from .executor import QueryExecutor
from .llm import Models
from .models import ApprovalDecision, DomainError, Principal, QueryRequest
from .store import Store
from .workflow import Context, build_graph

logger = logging.getLogger("sql_analytics")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s level=%(levelname)s %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False
REQUESTS = Counter("analytics_http_requests_total", "Requests", ["method", "route", "status"])
LATENCY = Histogram("analytics_http_seconds", "Request latency", ["route"])


@asynccontextmanager
async def capacity(semaphore):
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=1)
    except TimeoutError as exc:
        raise DomainError("service_busy_retry_later", 503) from exc
    try:
        yield
    finally:
        semaphore.release()


def csv_bytes(payload):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)

    def safe(value):
        text = "" if value is None else str(value)
        return (
            "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")) else text
        )

    writer.writerow([safe(c) for c in payload["columns"]])
    for row in payload["rows"]:
        writer.writerow([safe(row.get(c)) for c in payload["columns"]])
    return stream.getvalue().encode("utf-8-sig")


def create_app(settings=None):
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app):
        async with AsyncExitStack() as stack:
            control = await stack.enter_async_context(
                AsyncConnectionPool(
                    settings.control_dsn.get_secret_value(),
                    min_size=1,
                    max_size=24,
                    timeout=5,
                    open=False,
                    kwargs={"autocommit": True, "row_factory": dict_row},
                )
            )
            query = await stack.enter_async_context(
                AsyncConnectionPool(
                    settings.query_dsn.get_secret_value(),
                    min_size=1,
                    max_size=settings.max_concurrent_queries,
                    timeout=5,
                    open=False,
                    kwargs={"autocommit": True, "row_factory": dict_row},
                )
            )
            await control.wait(timeout=10)
            await query.wait(timeout=10)
            async with query.connection() as conn:
                cur = await conn.execute(
                    "SELECT rolsuper,rolbypassrls,rolinherit FROM pg_roles WHERE rolname=current_user"
                )
                role = await cur.fetchone()
                if not role or any(role.values()):
                    raise RuntimeError("Query login must be NOSUPERUSER NOBYPASSRLS NOINHERIT")
            saver = await stack.enter_async_context(
                AsyncPostgresSaver.from_conn_string(settings.checkpoint_dsn.get_secret_value())
            )
            # Migrations, including saver.setup(), are run by bootstrap, not on API startup.
            store = Store(control)
            models = Models(settings, store)
            stack.push_async_callback(models.close)
            app.state.store = store
            app.state.graph = build_graph(
                settings, store, QueryExecutor(query, settings), models, saver
            )
            app.state.verifier = TokenVerifier(settings)
            app.state.semaphore = asyncio.Semaphore(settings.max_concurrent_queries)
            yield

    app = FastAPI(title="Secure SQL Analytics", version="1.0.0", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse({"detail": exc.code}, status_code=exc.status)

    @app.middleware("http")
    async def observe(request: Request, call_next):
        request_id = str(uuid4())
        started = time.monotonic()
        response = await call_next(request)
        route = request.scope.get("route")
        route_name = route.path if route else "unmatched"
        REQUESTS.labels(request.method, route_name, response.status_code).inc()
        LATENCY.labels(route_name).observe(time.monotonic() - started)
        response.headers.update(
            {
                "X-Request-ID": request_id,
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
            }
        )
        logger.info(
            "request_id=%s method=%s route=%s status=%s",
            request_id,
            request.method,
            route_name,
            response.status_code,
        )
        return response

    @app.get("/health/live")
    async def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready(request: Request):
        async with request.app.state.store.pool.connection() as conn:
            await conn.execute("SELECT 1 FROM control.runs LIMIT 0")
        return {"status": "ready"}

    @app.get("/v1/me")
    async def me(p: Principal = Depends(require("analytics:query"))):
        return {"subject": p.subject, "permissions": p.permissions, "datasets": p.datasets}

    async def run_workflow(request, run, p):
        store, graph = request.app.state.store, request.app.state.graph
        async with capacity(request.app.state.semaphore), store.run_lock(run["id"]):
            run = await store.owned_run(run["id"], p)
            if run["status"] in {"completed", "clarification"}:
                return {"run_id": str(run["id"]), "status": run["status"], **run["response"]}
            config = {"configurable": {"thread_id": str(run["id"])}, "recursion_limit": 20}
            snapshot = await graph.aget_state(config)
            initial = (
                None if snapshot.values else {"run_id": str(run["id"]), "question": run["question"]}
            )
            await store.set_status(run["id"], "running")
            try:
                async with asyncio.timeout(settings.request_timeout_seconds):
                    state = await graph.ainvoke(
                        initial, config, context=Context(p), durability="sync"
                    )
                # Revocation/policy changes during the request invalidate delivery too.
                fresh = await store.principal(p.identity_tenant, p.subject)
                if fresh is None or fresh.fingerprint != p.fingerprint:
                    raise DomainError("permissions_changed_submit_new_query", 409)
                if state["intent"]["needs_clarification"]:
                    status, response = "clarification", {"answer": state["intent"]["clarification"]}
                else:
                    result = await store.result(run["id"])
                    status = "completed"
                    response = {
                        "answer": state["answer"],
                        "sql": state["validated_sql"],
                        "assumptions": state["candidate"]["assumptions"],
                        "chart": state["chart"],
                        **result["payload"],
                    }
                await store.set_status(run["id"], status, response=response)
                await store.audit(p.subject, "query", run["id"], status)
                return {"run_id": str(run["id"]), "status": status, **response}
            except TimeoutError as exc:
                await store.set_status(run["id"], "failed", error="request_deadline_exceeded")
                raise DomainError("request_deadline_exceeded", 504) from exc
            except DomainError as exc:
                await store.set_status(run["id"], "failed", error=exc.code)
                await store.audit(p.subject, "query", run["id"], exc.code)
                raise
            except DatabaseError as exc:
                await store.set_status(run["id"], "failed", error="database_query_failed")
                raise DomainError("database_query_failed", 503) from exc
            except Exception as exc:
                # Do not expose provider messages, SQL parameters or database diagnostics.
                logger.error(
                    "workflow_failed run_id=%s error_type=%s", run["id"], type(exc).__name__
                )
                await store.set_status(run["id"], "failed", error="workflow_failed")
                raise DomainError("workflow_failed", 500) from exc

    @app.post("/v1/queries")
    async def query(
        body: QueryRequest,
        request: Request,
        idempotency_key: UUID = Header(),
        p: Principal = Depends(require("analytics:query")),
    ):
        store = request.app.state.store
        await store.rate_limit(p, settings.requests_per_minute)
        run = await store.create_run(p, idempotency_key, body.question)
        return await run_workflow(request, run, p)

    @app.get("/v1/queries")
    async def history(request: Request, p: Principal = Depends(require("analytics:query"))):
        return jsonable_encoder(await request.app.state.store.list_runs(p))

    @app.get("/v1/queries/{run_id}")
    async def status(
        run_id: UUID, request: Request, p: Principal = Depends(require("analytics:query"))
    ):
        run = await request.app.state.store.owned_run(run_id, p)
        return {
            "run_id": str(run_id),
            "status": run["status"],
            "error": run["error_code"],
            **(run["response"] or {}),
        }

    @app.post("/v1/queries/{run_id}/resume")
    async def resume(
        run_id: UUID, request: Request, p: Principal = Depends(require("analytics:query"))
    ):
        await request.app.state.store.rate_limit(p, settings.requests_per_minute)
        run = await request.app.state.store.owned_run(run_id, p)
        return await run_workflow(request, run, p)

    @app.post("/v1/queries/{run_id}/export-request")
    async def export_request(
        run_id: UUID, request: Request, p: Principal = Depends(require("analytics:export"))
    ):
        result = await request.app.state.store.request_export(run_id, p)
        await request.app.state.store.audit(p.subject, "export_requested", run_id, "pending")
        return jsonable_encoder(result)

    @app.get("/v1/approvals")
    async def approvals(request: Request, p: Principal = Depends(require("approvals:review"))):
        return jsonable_encoder(await request.app.state.store.pending_approvals(p))

    @app.post("/v1/approvals/{approval_id}")
    async def decide(
        approval_id: UUID,
        body: ApprovalDecision,
        request: Request,
        p: Principal = Depends(require("approvals:review")),
    ):
        result = await request.app.state.store.decide(approval_id, p, body.approved)
        await request.app.state.store.audit(
            p.subject, "approval_decision", approval_id, result["status"]
        )
        return jsonable_encoder(result)

    @app.get("/v1/queries/{run_id}/export")
    async def export(
        run_id: UUID, request: Request, p: Principal = Depends(require("analytics:export"))
    ):
        payload = await request.app.state.store.approved_result(run_id, p)
        await request.app.state.store.audit(p.subject, "export_download", run_id, "allowed")
        return Response(
            csv_bytes(payload),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="analytics-{run_id}.csv"'},
        )

    @app.get("/metrics")
    async def metrics(p: Principal = Depends(require("operations:metrics"))):
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app
