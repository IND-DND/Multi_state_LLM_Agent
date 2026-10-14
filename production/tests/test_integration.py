import os
from uuid import uuid4

import psycopg
import pytest
from conftest import token
from fastapi.testclient import TestClient

from sql_analytics.config import Settings
from sql_analytics.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    if os.getenv("RUN_DATABASE_TESTS") != "1":
        pytest.skip("Set RUN_DATABASE_TESTS=1 after bootstrapping PostgreSQL")
    with TestClient(create_app(Settings())) as test_client:
        yield test_client


def headers(subject="analyst-north", key=None):
    return {
        "Authorization": "Bearer " + token(subject, secret=os.environ["DEMO_JWT_SECRET"]),
        "Idempotency-Key": str(key or uuid4()),
    }


def query(client, subject="analyst-north", text="total revenue", key=None):
    response = client.post("/v1/queries", headers=headers(subject, key), json={"question": text})
    assert response.status_code == 200, response.text
    return response.json()


def test_real_rls_tenant_and_region_isolation(client):
    assert query(client)["rows"] == [{"revenue": "300.00"}]
    assert query(client, "manager")["rows"] == [{"revenue": "1000.00"}]
    assert query(client, "other-tenant")["rows"] == [{"revenue": "9000.00"}]


def test_monthly_and_category_charts(client):
    month = query(client, text="monthly revenue")
    assert month["chart"]["kind"] == "line"
    assert len(month["rows"]) == 2
    category = query(client, text="revenue by category")
    assert category["rows"] == [{"category": "stationery", "revenue": "300.00"}]


def test_authentication_and_unknown_principal(client):
    assert client.post("/v1/queries", json={"question": "revenue"}).status_code == 401
    assert client.get("/v1/me", headers=headers("unknown-user")).status_code == 403


def test_history_ownership_and_idempotency(client):
    key = uuid4()
    result = query(client, key=key)
    assert query(client, key=key)["run_id"] == result["run_id"]
    run_id = result["run_id"]
    assert client.get(f"/v1/queries/{run_id}", headers=headers("other-tenant")).status_code == 404
    assert (
        client.post(f"/v1/queries/{run_id}/resume", headers=headers("manager")).status_code == 404
    )
    assert (
        client.post(
            "/v1/queries", headers=headers(key=key), json={"question": "monthly revenue"}
        ).status_code
        == 409
    )


def test_export_requires_independent_approval_and_owner(client):
    result = query(client)
    run_id = result["run_id"]
    path = f"/v1/queries/{run_id}"
    assert client.get(path + "/export", headers=headers()).status_code == 403
    approval = client.post(path + "/export-request", headers=headers()).json()["id"]
    assert (
        client.post(
            f"/v1/approvals/{approval}", headers=headers("other-tenant"), json={"approved": True}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/v1/approvals/{approval}", headers=headers("manager"), json={"approved": True}
        ).status_code
        == 200
    )
    response = client.get(path + "/export", headers=headers())
    assert response.status_code == 200 and "300.00" in response.text
    assert client.get(path + "/export", headers=headers("manager")).status_code == 404


def test_self_approval_and_viewer_export_denied(client):
    result = query(client, "manager")
    approval = client.post(
        f"/v1/queries/{result['run_id']}/export-request", headers=headers("manager")
    ).json()["id"]
    assert (
        client.post(
            f"/v1/approvals/{approval}", headers=headers("manager"), json={"approved": True}
        ).status_code
        == 409
    )
    viewer = query(client, "viewer")
    assert (
        client.post(
            f"/v1/queries/{viewer['run_id']}/export-request", headers=headers("viewer")
        ).status_code
        == 403
    )


def test_policy_change_invalidates_cached_result(client):
    result = query(client)
    with psycopg.connect(os.environ["MIGRATION_DSN"], autocommit=True) as conn:
        conn.execute(
            "UPDATE control.principals SET policy_version=policy_version+1 WHERE subject='analyst-north'"
        )
    assert client.get(f"/v1/queries/{result['run_id']}", headers=headers()).status_code == 409


def test_db_roles_have_no_write_or_control_access(client):
    with psycopg.connect(os.environ["QUERY_DSN"], autocommit=True) as conn:
        with conn.transaction():
            conn.execute("SET LOCAL ROLE scope_analyst_north")
            assert (
                conn.execute(
                    "SELECT sum(net_amount) FROM analytics.sales WHERE status='completed'"
                ).fetchone()[0]
                == 300
            )
        with pytest.raises(psycopg.Error):
            conn.execute("SELECT * FROM control.principals")
        with pytest.raises(psycopg.Error):
            conn.execute("DELETE FROM analytics.sales")
        # Gateway has NOINHERIT: without SET ROLE it cannot read any dataset.
        with pytest.raises(psycopg.Error):
            conn.execute("SELECT * FROM analytics.sales")


def test_clarification(client):
    assert query(client, text="what should I do?")["status"] == "clarification"


def test_restart_reads_durable_result(client):
    result = query(client)
    # A second application instance opens a fresh checkpoint connection and pools.
    with TestClient(create_app(Settings())) as restarted:
        response = restarted.post(f"/v1/queries/{result['run_id']}/resume", headers=headers())
        assert response.status_code == 200
        assert response.json()["rows"] == result["rows"]


def test_history_listing_is_owner_scoped(client):
    own = query(client)
    mine = client.get("/v1/queries", headers=headers()).json()
    other = client.get("/v1/queries", headers=headers("other-tenant")).json()
    assert own["run_id"] in {item["id"] for item in mine}
    assert own["run_id"] not in {item["id"] for item in other}
