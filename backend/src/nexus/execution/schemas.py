from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, JsonValue

from nexus.workflows.schemas import Issue


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExecutionStart(Strict):
    input: JsonValue = None
    mode: Literal["full", "node", "from_node"] = "full"
    node_id: str | None = None
    allow_paid: bool = False


class ApprovalDecision(Strict):
    decision: Literal["approved", "rejected"]


class CheckpointRestore(Strict):
    checkpoint_id: str


class ExecutionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workflow_id: str | None
    workflow_name: str
    workflow_version: int | None
    session_id: str
    status: str
    mode: str
    allow_paid: bool
    entry_node: str | None
    error: str | None
    error_node: str | None
    metrics: dict[str, Any]
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None


class NodeExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    node_id: str
    node_type: str
    attempt: int
    status: str
    input: Any
    output: Any
    error: str | None
    usage: dict[str, Any] | None
    started_at: datetime
    ended_at: datetime | None


class ExecutionDetail(ExecutionSummary):
    input: Any
    output: Any
    nodes: list[NodeExecutionRead]
    pending_approvals: list[dict[str, Any]] = []


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    type: str
    node_id: str | None
    payload: dict[str, Any]
    created_at: datetime


class CheckpointRead(BaseModel):
    checkpoint_id: str
    next: list[str]
    created_at: str | None


class StartRejected(BaseModel):
    detail: str
    issues: list[Issue]
