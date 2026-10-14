import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Principal(StrictModel):
    subject: str
    identity_tenant: str
    tenant_id: UUID
    db_role: str
    permissions: list[str]
    datasets: list[str]
    policy_version: int

    @property
    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json")
        payload["permissions"] = sorted(self.permissions)
        payload["datasets"] = sorted(self.datasets)
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class QueryRequest(StrictModel):
    question: str = Field(min_length=3, max_length=2000)


class Intent(StrictModel):
    clarified_question: str = Field(max_length=3000)
    needs_clarification: bool
    clarification: str = Field(max_length=500)


class SQLCandidate(StrictModel):
    sql: str = Field(min_length=1, max_length=12000)
    assumptions: list[str] = Field(max_length=8)


class ChartSpec(StrictModel):
    kind: Literal["table", "bar", "line", "scatter"]
    x: str | None = None
    y: str | None = None


class Narrative(StrictModel):
    text: str = Field(max_length=2500)


class ApprovalDecision(StrictModel):
    approved: bool


class DomainError(Exception):
    def __init__(self, code: str, status: int = 400):
        self.code = code
        self.status = status
        super().__init__(code)
