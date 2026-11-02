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
    step: bool = False


class ResumeRequest(Strict):
    # In a step-through run, finish the run instead of advancing one node.
    run_to_end: bool = False


class ReplayRequest(Strict):
    """Node id -> configuration values to change. Everything else stays as recorded."""

    overrides: dict[str, dict[str, Any]] = {}
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
    step_mode: bool
    replay_of: str | None
    overrides: dict[str, Any] | None
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


class CheckpointState(BaseModel):
    checkpoint_id: str
    next: list[str]
    outputs: dict[str, Any]
    variables: dict[str, Any]
    errors: dict[str, Any]


class TraceSpan(BaseModel):
    id: str
    node_id: str
    label: str
    node_type: str
    status: str
    attempt: int
    start_ms: int
    duration_ms: int | None
    model: str | None
    tokens: int | None
    cost_usd: float | None
    error: str | None


class TraceFailure(BaseModel):
    node_id: str | None
    label: str | None
    message: str
    input: Any = None


class ExecutionTrace(BaseModel):
    execution_id: str
    status: str
    recorded: bool
    replay_of: str | None
    overrides: dict[str, Any] | None
    duration_ms: int | None
    spans: list[TraceSpan]
    failure: TraceFailure | None


class CompareSide(BaseModel):
    status: str | None
    duration_ms: int | None
    model: str | None
    tokens: int | None
    cost_usd: float | None
    output: Any = None


class CompareRow(BaseModel):
    node_id: str
    label: str
    left: CompareSide
    right: CompareSide
    same_status: bool
    same_output: bool
    config_changed: bool


class ExecutionComparison(BaseModel):
    left_id: str
    right_id: str
    left_status: str
    right_status: str
    rows: list[CompareRow]


class StartRejected(BaseModel):
    detail: str
    issues: list[Issue]
