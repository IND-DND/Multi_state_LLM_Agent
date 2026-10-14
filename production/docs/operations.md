# Operations and recovery

## Request lifecycle

POST `/v1/queries` requires a UUID idempotency key. The uniqueness scope is identity
tenant + subject + key. Reusing a key for another question returns 409. Concurrent
workers use a PostgreSQL advisory lock on the run ID. A completed request returns its
saved response. Failed/interrupted requests can be resumed by the owner with the same
authorization fingerprint. Every resume remains subject to the total model-call budget.

Checkpoint writes use LangGraph `durability="sync"`. On worker failure, the database
connection closes and releases its lock. An interrupted run may still display `running`;
an explicit resume attempts the lock, then recovers the graph. There is no autonomous
background recovery daemon in this version. A request timeout cancels the coroutine;
the PostgreSQL statement timeout independently bounds database work.

A SELECT may replay if the worker crashes before result persistence. Once a snapshot
exists it is reused. For reproducibility across that earlier crash window, query a
versioned warehouse snapshot or use an explicit business-data version; an ordinary
live PostgreSQL query cannot promise the same answer after the underlying data changes.

## Failures

| Symptom | Action |
|---|---|
| 401 | Obtain a fresh API access token; check audience/issuer/expiry |
| 403 | Check API scope and provisioned permissions; do not broaden model prompts |
| 409 run_in_progress | Poll the run; retry resume after the existing worker finishes/disconnects |
| 409 permissions_changed | Submit a new query; old approvals/results are intentionally invalid |
| 422 SQL error | Refine the question or extend the approved catalog/grammar with tests |
| 429 | Back off until the next minute; inspect per-principal usage |
| 503 | Check model service, database connectivity, and DB role configuration |
| 504 | Refine the query; inspect the query plan and configured deadline |

Provider 429/5xx/network errors get at most one transient retry with jitter. SQL parse
and unknown-column errors get at most two repairs. Authorization failures are never
repaired by changing the permissions. Failed presentation calls fall back to the table.

## Monitoring

`/health/live` checks the process. `/health/ready` checks the control database.
Authenticated `/metrics` exposes HTTP request counts and latency histograms by bounded
route/method/status labels. It does not expose subjects or SQL labels. This endpoint
uses the standard Prometheus Python registry; run one Uvicorn worker per container
and scale with replicas, or configure Prometheus multiprocess collection explicitly.

Audit rows record query outcomes, export requests/decisions, and downloads. Authentication
failures are visible in HTTP metrics; database audit entries are for authenticated actions.
Persisted `model_calls` gives a request-level call budget. Detailed token-cost telemetry
and automatic provider billing reconciliation are future integrations, not implemented.

Alert on elevated 5xx/504, p95 request latency, rate rejection spikes, PostgreSQL connection
pressure, statement timeouts, failed backup restores, and model-provider errors. Establish
latency/cost targets from your own load tests; this repository contains no invented SLO results.

## Retention and backup

Use `scripts/retention.py --days 30` from an administrative maintenance job, after choosing
your retention period. It deletes expired run snapshots and their corresponding graph
checkpoints, plus old rate counters; it leaves audit retention to the organization's policy.
Back up the business data, control schema, and checkpoint schema consistently. Restore
to a disposable environment and test authorization and replay before declaring recovery complete.
