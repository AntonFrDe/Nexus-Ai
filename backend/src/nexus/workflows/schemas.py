from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nexus.workflows.migrations import CURRENT_SCHEMA_VERSION

MAX_WORKFLOW_BYTES = 5_000_000
EXPORT_FORMAT = "nexus.workflow"
Identifier = Annotated[str, Field(min_length=1, max_length=120)]
Name = Annotated[str, Field(min_length=1, max_length=120)]
Description = Annotated[str, Field(max_length=2000)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Position(Strict):
    x: float
    y: float


class WorkflowNode(Strict):
    """Topology plus instance data. Behavior belongs to the node type, referenced by name."""

    id: Identifier
    type: Identifier
    position: Position
    label: str = Field(default="", max_length=200)
    config: dict[str, Any] = Field(default_factory=dict)
    runtime: dict[str, Any] = Field(default_factory=dict)
    permissions: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    parent_id: str | None = None
    width: float | None = None
    height: float | None = None


class WorkflowEdge(Strict):
    id: Identifier
    source: Identifier
    source_port: Identifier
    target: Identifier
    target_port: Identifier
    label: str = Field(default="", max_length=200)


class WorkflowGraph(Strict):
    schema_version: Literal[1] = CURRENT_SCHEMA_VERSION
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    policies: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _bounded(self) -> Self:
        if len(self.model_dump_json()) > MAX_WORKFLOW_BYTES:
            raise ValueError(f"workflow exceeds {MAX_WORKFLOW_BYTES} bytes")
        return self


class WorkflowCreate(Strict):
    name: Name
    description: Description = ""


class WorkflowContent(WorkflowGraph):
    """A complete editable document, as saved by the client."""

    name: Name
    description: Description = ""


class WorkflowDocument(WorkflowContent):
    id: str
    created_at: datetime
    updated_at: datetime


class WorkflowSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


class WorkflowExport(Strict):
    """Portable file format; carries no database IDs."""

    format: Literal["nexus.workflow"] = EXPORT_FORMAT
    workflow: WorkflowContent


class VersionCreate(Strict):
    label: str = Field(default="", max_length=200)


class VersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    number: int
    label: str
    created_at: datetime


class Issue(BaseModel):
    severity: Literal["error", "warning"]
    code: str
    message: str
    node_id: str | None = None
    edge_id: str | None = None
    field: str | None = None


class ValidationReport(BaseModel):
    valid: bool
    issues: list[Issue]
