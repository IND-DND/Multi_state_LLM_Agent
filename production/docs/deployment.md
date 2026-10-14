# Deploying the service

## Entra registrations

1. Register a single-tenant API application. Configure v2 access tokens and expose the
   delegated scope `api://<API client ID>/analytics.access`.
2. Register a separate public client for the included Streamlit UI; enable device-code
   public client flows, grant the delegated API scope, and obtain administrator consent
   according to tenant policy. The UI uses MSAL device-code sign-in and keeps its token
   in the server-side Streamlit session. It does not accept passwords.
3. Set `ENTRA_TENANT_ID`, `API_AUDIENCE` (the API client ID for v2 tokens), `UI_CLIENT_ID`
   and `API_SCOPE`. Verify the actual access token audience in your tenant configuration.
4. Apply MFA/Conditional Access through Entra. Some organizations block device-code
   flows. For those organizations, replace the Streamlit sign-in with an approved
   authorization-code + PKCE client/BFF; the API token validation remains the same.
5. Provision the user's Entra **oid**, not their email address, using the script below.
   A valid Entra token alone grants no access until the user is provisioned.

```bash
python scripts/provision_user.py \
  --identity-tenant <entra-directory-uuid> \
  --subject <user-object-uuid> \
  --business-tenant <business-tenant-uuid> \
  --regions north,south \
  --datasets sales,customers,products \
  --permissions analytics:query,analytics:export
```

Run with `MIGRATION_DSN` available only to the administrator's process. Pass the
same inputs with `--disable` to revoke access. Scope changes and revocation increment
the authorization version and invalidate old results. Tenant/region/dataset changes
must use this provisioning path or perform the equivalent changes atomically.

## Azure resource mapping

| Service | Configuration |
|---|---|
| Azure Container Apps | Separate API and UI apps; internal API ingress; UI behind approved TLS ingress |
| Azure Database for PostgreSQL | Dedicated reporting database; private networking; TLS; backups/PITR |
| Azure OpenAI | Approved model deployment; private endpoint and controlled egress where required |
| Azure Key Vault | Runtime DSNs and provider key; no administrator DSN in runtime apps |
| Azure Container Registry | Built application image; managed identity for image pulls |
| Azure Monitor | Structured application logs, metrics collection, alerts, retention |
| Entra ID | User authentication and Conditional Access |

This repository supplies container packaging and application configuration; it does
not automatically create billable Azure resources. Network, DNS, certificates, model
capacity, identities, and data retention depend on your Azure subscription and policies.

## Deployment sequence

1. Build and scan the Docker image; push it to your registry with a commit-SHA tag.
   Use digest references for releases and pin the base image digest in your build pipeline.
2. Provision private PostgreSQL connectivity and separate migration, query, control,
   and checkpoint identities. The API must never use the migration identity.
3. Run `python scripts/bootstrap.py` **without `--demo`** as a one-off migration job.
   This initial migration is idempotent; future schema changes need new numbered
   migrations and a tested rollback/forward-compatibility strategy.
4. Load your data into the curated `analytics` tables through a separate ingestion role.
   Adapt the schema/catalog and tests to your real tables before loading customer data.
5. Provision scopes and users. Database policies are default-deny when no role scope exists.
6. Inject runtime settings using platform secret references. Enable `ENVIRONMENT=production`.
   Configure the mounted CA chain if needed and require `sslmode=verify-full` on all DSNs.
7. Deploy the API and UI. Set `ALLOWED_HOSTS` to the API's internal hostname; set `API_URL`
   in the UI to that endpoint. Enable HTTPS at ingress and between services where required.
8. Run smoke tests using distinct Entra users with different scopes, then run load,
   adversarial SQL, restore, and worker-restart tests in staging.
9. Set minimum replicas and connection-pool budgets against the PostgreSQL connection limit.
   The per-process semaphore does not replace an organization-wide concurrency policy.

The code currently uses secret-injected PostgreSQL credentials and provider API keys.
Platform managed identity can resolve Key Vault/registry access; automatic PostgreSQL
token refresh and Azure model token authentication are not implemented in this version.
Do not describe those integrations as already implemented.

## Credential rotation

The bootstrap script creates missing roles but does not silently rotate existing
passwords. Rotate each password with an administrative `ALTER ROLE`, update its
secret reference, and restart the affected runtime. Never pass secrets in command-line
arguments or commit `.env`. Test overlap/rollback before production rotation.

## Official references

- https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens
- https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens
- https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/
- https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- https://docs.langchain.com/oss/python/langgraph/persistence
