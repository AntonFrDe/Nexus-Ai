from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

MAX_DOCUMENT_BYTES = 2_000_000
EXPORT_FORMAT = "nexus.workspace"
EXPORT_SCHEMA_VERSION = 1


def _bounded(value: dict[str, Any] | None) -> dict[str, Any] | None:
    import json

    if value is not None and len(json.dumps(value)) > MAX_DOCUMENT_BYTES:
        raise ValueError(f"document exceeds {MAX_DOCUMENT_BYTES} bytes")
    return value


def _layout_shape(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Layouts are Dockview documents: opaque here, but their envelope must be present."""
    if value is not None and not {"grid", "panels"} <= value.keys():
        raise ValueError("layout must contain 'grid' and 'panels'")
    return value


Document = Annotated[dict[str, Any], AfterValidator(_bounded)]
Layout = Annotated[dict[str, Any] | None, AfterValidator(_bounded), AfterValidator(_layout_shape)]
Name = Annotated[str, Field(min_length=1, max_length=120)]
Description = Annotated[str, Field(max_length=2000)]


class WorkspaceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    description: Description = ""
    preset: str | None = Field(default=None, max_length=64)


class WorkspaceUpdate(BaseModel):
    """Partial update: only fields sent by the client are applied."""

    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    description: Description | None = None
    preset: str | None = Field(default=None, max_length=64)
    layout: Layout = None
    panel_states: Document | None = None
    preferences: Document | None = None
    position: int | None = None


class WorkspaceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    preset: str | None
    position: int
    created_at: datetime
    updated_at: datetime


class WorkspaceDetail(WorkspaceSummary):
    layout: dict[str, Any] | None
    panel_states: dict[str, Any]
    preferences: dict[str, Any]


class WorkspaceExportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    description: Description = ""
    preset: str | None = Field(default=None, max_length=64)
    layout: Layout = None
    panel_states: Document = Field(default_factory=dict)
    preferences: Document = Field(default_factory=dict)


class WorkspaceExport(BaseModel):
    """Portable file format; carries no IDs so imports never collide."""

    model_config = ConfigDict(extra="forbid")

    format: Literal["nexus.workspace"] = EXPORT_FORMAT
    schema_version: Literal[1] = EXPORT_SCHEMA_VERSION
    workspace: WorkspaceExportBody
