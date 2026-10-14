# Security model

## Trust boundaries

The browser, question, generated SQL, database text, and model response are untrusted.
The API verifies the token and resolves entitlements from `control.principals`. Trusted
application code supplies the principal in LangGraph runtime context; no token is saved
in a checkpoint. A separate credential opens the query pool, then `SET LOCAL ROLE`
selects the administrator-provisioned scope role inside a read-only transaction.

RLS checks `current_user` against `app_private.role_scopes` through a fixed-search-path
SECURITY DEFINER function owned by the migration administrator. Scope roles cannot edit
that table. The gateway is NOINHERIT and cannot read analytics data without assuming a
scope role. Application SQL cannot contain SET/RESET, arbitrary functions, or multiple
statements. The role name comes from the entitlement table and is identifier-quoted.

The gateway is a trusted service credential capable of assuming multiple scope roles.
Compromise of that credential or the API process can cross scopes. RLS here protects
against incorrect/generated queries, not a fully compromised backend. For stronger
isolation use separate tenant databases/credentials and execution services.

## Defense coverage

| Threat | Enforced controls | Additional operational requirement |
|---|---|---|
| Forged identity | Fixed RS256 algorithm/JWKS, issuer/audience/tenant/expiry/scope checks | Entra MFA and tenant policies |
| Prompt asks for another tenant | Server-owned principal, database RLS | Provision/review scope mappings |
| SQL writes or unsafe functions | Strict AST subset, role grants, read-only transaction | Dedicated reporting database; no unsafe extensions |
| History/result ID guessing | Subject and identity-tenant ownership checks | Protect backups and checkpoint storage |
| Export approval bypass | Owner + export permission + independent reviewer + digest/version/expiry | Define reviewer assignment and review practice |
| Long-running SQL | Statement and lock timeouts, pool/concurrency/result limits | Workload isolation, indexes, capacity alarms |
| Retry storms | Persisted call budget, bounded retry/repair, rate counter | Gateway limits and model-provider quotas |
| Secrets/data in logs | No raw questions, tokens, SQL, result rows, or exception details in app logs | Disable verbose SDK/proxy request logging |
| Spreadsheet formula execution | Escape formula-like CSV cells and headers | Treat downloaded files as data |

## Data storage

Control tables and checkpoints include questions, SQL, and results. Encrypt disks and
backups; keep PostgreSQL private; use distinct roles; set a retention schedule. Audit
inserts use a role with no UPDATE/DELETE grant on the audit table, but this is not a
cryptographically tamper-proof ledger. Forward audit events to your immutable retention
system when required. Table owners and administrators remain privileged.

JWT local validation does not immediately revoke an otherwise valid access token when
a user signs out. Application entitlements are checked every request, and the enabled
flag/policy version provides immediate application-level revocation for new requests.
The service rechecks authorization before delivering a newly generated result.

## Before real-data release

Run the integration tests against the exact PostgreSQL/server and dependency versions
you deploy. Review catalog grain, approved joins, RLS plans, permissions, model data
handling, backup restores, secret rotation, and rate-limit behavior under load. Use an
approved security review for expanding the SQL grammar. No automated test suite proves
all prompt-injection or SQL-parser edge cases are impossible.
