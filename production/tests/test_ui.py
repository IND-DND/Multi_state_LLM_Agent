from pathlib import Path

import httpx
from streamlit.testing.v1 import AppTest


def test_demo_ui_query_and_identity_switch(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DEMO_JWT_SECRET", "ui-test-secret-not-production-" * 2)

    def request(method, url, **kwargs):
        if url.endswith("/v1/me"):
            body = {"permissions": ["analytics:query"], "datasets": ["sales"]}
        elif method == "GET" and url.endswith("/v1/queries"):
            body = []
        else:
            body = {
                "run_id": "00000000-0000-0000-0000-000000000001",
                "status": "completed",
                "answer": "Revenue is INR 300.",
                "sql": "SELECT SUM(net_amount) FROM analytics.sales",
                "assumptions": [],
                "columns": ["revenue"],
                "rows": [{"revenue": "300.00"}],
                "chart": {"kind": "table"},
            }
        return httpx.Response(200, json=body)

    monkeypatch.setattr(httpx, "request", request)
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "ui/app.py"), default_timeout=20
    ).run()
    assert not app.exception
    app.text_input[0].input("total revenue").run()
    next(button for button in app.button if button.label == "Analyze").click().run()
    assert not app.exception
    assert app.dataframe[0].value.iloc[0]["revenue"] == "300.00"
    app.sidebar.selectbox[0].select("other-tenant").run()
    assert not app.exception
    assert len(app.dataframe) == 0
