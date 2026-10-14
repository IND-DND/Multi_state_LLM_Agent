from copy import deepcopy
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from sql_analytics.llm import Models
from sql_analytics.models import DomainError, Principal
from sql_analytics.sql_guard import validate_sql
from sql_analytics.workflow import Context, build_graph


class MemoryStore:
    def __init__(self):
        self.calls = 0
        self.results = {}
        self.crash_after_save = False

    async def reserve_model_call(self, run_id, maximum):
        if self.calls >= maximum:
            raise DomainError("model_call_budget_exhausted", 422)
        self.calls += 1

    async def result(self, run_id):
        return deepcopy(self.results.get(run_id))

    async def save_result(self, run_id, query_hash, fingerprint, payload):
        self.results.setdefault(
            run_id, {"query_hash": query_hash, "fingerprint": fingerprint, "payload": payload}
        )
        if self.crash_after_save:
            self.crash_after_save = False
            raise RuntimeError("simulated worker failure after durable result write")


class Executor:
    def __init__(self):
        self.calls = 0

    async def execute(self, sql, principal):
        self.calls += 1
        return validate_sql(sql, principal.datasets), {
            "columns": ["revenue"],
            "rows": [{"revenue": "300.00"}],
            "truncated": False,
        }


def principal():
    return Principal(
        subject="analyst",
        identity_tenant="demo",
        tenant_id="11111111-1111-1111-1111-111111111111",
        db_role="scope_analyst",
        permissions=["analytics:query"],
        datasets=["sales", "products", "customers"],
        policy_version=1,
    )


async def test_replay_reuses_saved_snapshot_after_worker_failure(settings):
    store, executor = MemoryStore(), Executor()
    saver = InMemorySaver()
    graph = build_graph(settings, store, executor, Models(settings, store), saver)
    run_id = str(uuid4())
    config = {"configurable": {"thread_id": run_id}}
    store.crash_after_save = True
    with pytest.raises(RuntimeError):
        await graph.ainvoke(
            {"run_id": run_id, "question": "total revenue"}, config, context=Context(principal())
        )
    assert executor.calls == 1
    # New graph instance uses the same checkpoint/result storage, simulating restart.
    recovered = build_graph(settings, store, executor, Models(settings, store), saver)
    state = await recovered.ainvoke(None, config, context=Context(principal()))
    assert state["answer"]
    assert executor.calls == 1
    assert store.calls == 4


async def test_model_budget_is_enforced_and_presentation_degrades(settings):
    settings.max_model_calls = 2
    store, executor = MemoryStore(), Executor()
    graph = build_graph(settings, store, executor, Models(settings, store), InMemorySaver())
    run_id = str(uuid4())
    state = await graph.ainvoke(
        {"run_id": run_id, "question": "revenue"},
        {"configurable": {"thread_id": run_id}},
        context=Context(principal()),
    )
    assert store.calls == 2
    assert state["chart"]["kind"] == "table"
    assert "unavailable" in state["answer"]


async def test_policy_failure_never_executes_or_repairs(settings):
    store, executor = MemoryStore(), Executor()
    user = principal()
    user.datasets = ["customers"]
    graph = build_graph(settings, store, executor, Models(settings, store), InMemorySaver())
    run_id = str(uuid4())
    with pytest.raises(DomainError, match="dataset_denied"):
        await graph.ainvoke(
            {"run_id": run_id, "question": "revenue"},
            {"configurable": {"thread_id": run_id}},
            context=Context(user),
        )
    assert executor.calls == 0
    assert store.calls == 2
