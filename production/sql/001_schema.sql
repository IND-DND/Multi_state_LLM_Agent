-- Apply as migration administrator, never as an API runtime login.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS app_private;
CREATE SCHEMA IF NOT EXISTS control;
REVOKE ALL ON SCHEMA app_private, control, analytics FROM PUBLIC;

CREATE TABLE IF NOT EXISTS app_private.role_scopes (
    db_role name NOT NULL, tenant_id uuid NOT NULL, region text NOT NULL,
    PRIMARY KEY (db_role, tenant_id, region)
);
CREATE OR REPLACE FUNCTION app_private.can_read(role_name name, tenant uuid, region_name text)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, app_private
AS $$ SELECT EXISTS (SELECT 1 FROM app_private.role_scopes
    WHERE db_role = role_name AND tenant_id = tenant AND region = region_name) $$;
REVOKE ALL ON FUNCTION app_private.can_read(name, uuid, text) FROM PUBLIC;

CREATE TABLE IF NOT EXISTS analytics.customers (
    customer_id integer PRIMARY KEY, tenant_id uuid NOT NULL, region text NOT NULL,
    segment text NOT NULL CHECK (length(segment) <= 80),
    UNIQUE (customer_id, tenant_id, region)
);
CREATE TABLE IF NOT EXISTS analytics.products (
    product_id integer PRIMARY KEY, tenant_id uuid NOT NULL, region text NOT NULL,
    product_name text NOT NULL CHECK (length(product_name) <= 160),
    category text NOT NULL CHECK (length(category) <= 80),
    UNIQUE (product_id, tenant_id, region)
);
CREATE TABLE IF NOT EXISTS analytics.sales (
    sale_id integer PRIMARY KEY, tenant_id uuid NOT NULL, region text NOT NULL,
    customer_id integer NOT NULL, product_id integer NOT NULL, sold_on date NOT NULL,
    quantity integer NOT NULL CHECK (quantity > 0), net_amount numeric(14,2) NOT NULL,
    status text NOT NULL CHECK (status IN ('completed','cancelled','refunded')),
    FOREIGN KEY (customer_id, tenant_id, region) REFERENCES analytics.customers(customer_id, tenant_id, region),
    FOREIGN KEY (product_id, tenant_id, region) REFERENCES analytics.products(product_id, tenant_id, region)
);
CREATE INDEX IF NOT EXISTS sales_scope_date ON analytics.sales(tenant_id, region, sold_on);

ALTER TABLE analytics.customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics.customers FORCE ROW LEVEL SECURITY;
ALTER TABLE analytics.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics.products FORCE ROW LEVEL SECURITY;
ALTER TABLE analytics.sales ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics.sales FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS scope_access ON analytics.customers;
CREATE POLICY scope_access ON analytics.customers FOR SELECT
    USING (app_private.can_read(current_user, tenant_id, region));
DROP POLICY IF EXISTS scope_access ON analytics.products;
CREATE POLICY scope_access ON analytics.products FOR SELECT
    USING (app_private.can_read(current_user, tenant_id, region));
DROP POLICY IF EXISTS scope_access ON analytics.sales;
CREATE POLICY scope_access ON analytics.sales FOR SELECT
    USING (app_private.can_read(current_user, tenant_id, region));

CREATE TABLE IF NOT EXISTS control.principals (
    identity_tenant text NOT NULL, subject text NOT NULL, tenant_id uuid NOT NULL,
    db_role name NOT NULL, permissions text[] NOT NULL, datasets text[] NOT NULL,
    policy_version integer NOT NULL DEFAULT 1, active boolean NOT NULL DEFAULT true,
    PRIMARY KEY (identity_tenant, subject)
);
CREATE TABLE IF NOT EXISTS control.runs (
    id uuid PRIMARY KEY, identity_tenant text NOT NULL, subject text NOT NULL,
    idempotency_key uuid NOT NULL, question text NOT NULL, fingerprint text NOT NULL,
    status text NOT NULL DEFAULT 'pending', model_calls integer NOT NULL DEFAULT 0,
    response jsonb, error_code text, created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (identity_tenant, subject, idempotency_key)
);
CREATE TABLE IF NOT EXISTS control.results (
    run_id uuid PRIMARY KEY REFERENCES control.runs(id) ON DELETE CASCADE,
    query_hash text NOT NULL, fingerprint text NOT NULL, payload jsonb NOT NULL,
    digest text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS control.approvals (
    id uuid PRIMARY KEY, run_id uuid UNIQUE NOT NULL REFERENCES control.runs(id) ON DELETE CASCADE,
    tenant_id uuid NOT NULL, digest text NOT NULL, fingerprint text NOT NULL,
    status text NOT NULL DEFAULT 'pending', reviewer text,
    expires_at timestamptz NOT NULL DEFAULT now() + interval '1 hour',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS control.rate_limits (
    identity_tenant text NOT NULL, subject text NOT NULL, bucket timestamptz NOT NULL,
    count integer NOT NULL, PRIMARY KEY (identity_tenant, subject, bucket)
);
CREATE TABLE IF NOT EXISTS control.audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at timestamptz NOT NULL DEFAULT now(), subject text NOT NULL,
    event text NOT NULL, resource_id text NOT NULL, outcome text NOT NULL
);
-- Runtime grants are applied by bootstrap.py after roles have been created.
