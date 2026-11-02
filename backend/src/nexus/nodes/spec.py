from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FieldKind(StrEnum):
    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    SLIDER = "slider"
    JSON = "json"
    CODE = "code"
    SECRET = "secret"
    ARRAY = "array"
    OBJECT = "object"


class Condition(BaseModel):
    """Show a field only while a sibling field holds one of these values."""

    field: str
    equals: list[Any]


class FieldSpec(BaseModel):
    """One configuration control; drives both the inspector and backend validation."""

    model_config = ConfigDict(extra="forbid")

    name: str
    label: str
    kind: FieldKind
    description: str = ""
    required: bool = False
    default: Any = None
    advanced: bool = False
    options: list[str] = Field(default_factory=list)
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    language: str | None = None
    item: "FieldSpec | None" = None
    fields: list["FieldSpec"] = Field(default_factory=list)
    visible_when: Condition | None = None

    @model_validator(mode="after")
    def _kind_requirements(self) -> Self:
        if self.kind in (FieldKind.SELECT, FieldKind.MULTI_SELECT) and not self.options:
            raise ValueError(f"{self.name}: {self.kind} needs options")
        if self.kind is FieldKind.ARRAY and self.item is None:
            raise ValueError(f"{self.name}: array needs item")
        if self.kind is FieldKind.SLIDER and (self.minimum is None or self.maximum is None):
            raise ValueError(f"{self.name}: slider needs minimum and maximum")
        return self


class PortSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    type: str = "any"
    required: bool = False
    multiple: bool = False


class NodeType(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    category: str
    description: str
    icon: str
    shape: str = "card"
    inputs: list[PortSpec] = Field(default_factory=list)
    outputs: list[PortSpec] = Field(default_factory=list)
    fields: list[FieldSpec] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    # Canvas-only nodes (groups, annotations) are ignored by graph rules and execution.
    executable: bool = True
    # A cycle is legal only when it passes through a node that bounds it.
    bounds_cycles: bool = False
