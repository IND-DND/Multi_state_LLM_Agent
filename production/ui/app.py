import os
import time
from uuid import uuid4

import httpx
import jwt
import msal
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Secure SQL Analytics", page_icon="📊", layout="wide")
st.title("Secure SQL Analytics")
st.caption("Ask about your authorized business data. Inspect the SQL, assumptions, and results.")
API = os.getenv("API_URL", "http://localhost:8000")
demo = os.getenv("AUTH_MODE") == "demo" and os.getenv("ENVIRONMENT") != "production"

if demo:
    st.warning(
        "Local demo: synthetic data and fixed example queries. Sign-in selection is for testing only."
    )
    subject = st.sidebar.selectbox(
        "Demo identity", ["analyst-north", "manager", "other-tenant", "viewer"]
    )
    if st.session_state.get("subject") != subject:
        st.session_state.clear()
        st.session_state.subject = subject
    now = int(time.time())
    st.session_state.token = jwt.encode(
        {
            "oid": subject,
            "tid": "demo",
            "iss": "sql-analytics-demo",
            "aud": "sql-analytics-api",
            "scp": "analytics.access",
            "iat": now,
            "nbf": now,
            "exp": now + 900,
        },
        os.environ["DEMO_JWT_SECRET"],
        algorithm="HS256",
    )
else:
    if "msal" not in st.session_state:
        st.session_state.msal = msal.PublicClientApplication(
            os.environ["UI_CLIENT_ID"],
            authority=f"https://login.microsoftonline.com/{os.environ['ENTRA_TENANT_ID']}",
        )
    if "token" not in st.session_state:
        if st.button("Sign in with Microsoft"):
            st.session_state.flow = st.session_state.msal.initiate_device_flow(
                scopes=[os.environ["API_SCOPE"]]
            )
        flow = st.session_state.get("flow")
        if flow:
            st.info(
                flow.get(
                    "message",
                    "Unable to start sign-in. Check the Entra public client configuration.",
                )
            )
            if "user_code" in flow and st.button("I have completed sign-in"):
                with st.spinner("Completing Microsoft sign-in…"):
                    result = st.session_state.msal.acquire_token_by_device_flow(flow)
                if "access_token" in result:
                    st.session_state.token = result["access_token"]
                    st.session_state.expires_at = time.time() + result.get("expires_in", 3600)
                    st.rerun()
                st.error("Sign-in did not complete. Start a new sign-in attempt.")
        st.stop()
    if time.time() >= st.session_state.get("expires_at", 0):
        st.session_state.clear()
        st.rerun()
    if st.sidebar.button("Sign out"):
        st.session_state.clear()
        st.rerun()


def api(method, path, **kwargs):
    try:
        response = httpx.request(
            method,
            API + path,
            headers={
                "Authorization": "Bearer " + st.session_state.token,
                **kwargs.pop("headers", {}),
            },
            timeout=60,
            **kwargs,
        )
        if response.is_error:
            st.error(
                f"Request failed ({response.status_code}): {response.json().get('detail', 'unavailable')}"
            )
            return None
        return response
    except httpx.HTTPError:
        st.error("The analytics API is unavailable. Check service health and retry.")
        return None


me = api("GET", "/v1/me")
if me is None:
    st.stop()
permissions = me.json()["permissions"]
st.sidebar.write("Datasets", me.json()["datasets"])
question = st.text_input("Your question", placeholder="Show monthly revenue")
if st.button("Analyze", type="primary", disabled=not question.strip()):
    if st.session_state.get("last_question") != question:
        st.session_state.key = str(uuid4())
        st.session_state.last_question = question
    with st.spinner("Validating access and analyzing…"):
        response = api(
            "POST",
            "/v1/queries",
            json={"question": question},
            headers={"Idempotency-Key": st.session_state.key},
        )
    if response:
        st.session_state.result = response.json()
if st.button("Start a fresh query"):
    st.session_state.pop("last_question", None)
    st.session_state.pop("result", None)
    st.rerun()
result = st.session_state.get("result")
if result:
    st.write(result["answer"])
    if result["status"] == "completed":
        st.caption("Run: " + result["run_id"])
        with st.expander("SQL and assumptions"):
            st.code(result["sql"], language="sql")
            st.write(result["assumptions"])
        frame = pd.DataFrame(result["rows"], columns=result["columns"])
        st.dataframe(frame, width="stretch")
        chart = result["chart"]
        if chart["kind"] != "table" and not frame.empty:
            try:
                plot_frame = frame.copy()
                plot_frame[chart["y"]] = pd.to_numeric(plot_frame[chart["y"]], errors="raise")
                renderer = {"line": px.line, "bar": px.bar, "scatter": px.scatter}[chart["kind"]]
                st.plotly_chart(renderer(plot_frame, x=chart["x"], y=chart["y"]), width="stretch")
            except (ValueError, TypeError, KeyError):
                st.info("These results are best viewed as a table.")
        if "analytics:export" in permissions:
            if st.button("Request CSV approval"):
                response = api("POST", f"/v1/queries/{result['run_id']}/export-request")
                if response:
                    st.info(f"Export approval: {response.json()['status']}")
            if st.button("Fetch approved CSV"):
                response = api("GET", f"/v1/queries/{result['run_id']}/export")
                if response:
                    st.download_button(
                        "Download CSV", response.content, "analytics.csv", "text/csv"
                    )
if "approvals:review" in permissions:
    with st.expander("Export approvals"):
        response = api("GET", "/v1/approvals")
        if response:
            for item in response.json():
                st.write(
                    f"Requester: {item['requester']} · Run: {item['run_id']} · Expires: {item['expires_at']}"
                )
                approve, deny = st.columns(2)
                for column, label, decision in [(approve, "Approve", True), (deny, "Deny", False)]:
                    if column.button(label, key=item["id"] + label):
                        api("POST", f"/v1/approvals/{item['id']}", json={"approved": decision})
                        st.rerun()
