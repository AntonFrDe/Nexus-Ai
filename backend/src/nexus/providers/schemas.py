from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from nexus.nodes.spec import FieldSpec

Name = Annotated[str, Field(min_length=1, max_length=120)]
SecretName = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.\-]{1,120}$")]
Endpoint = Annotated[str, Field(pattern=r"^https?://", max_length=500)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderCreate(Strict):
    type: str
    name: Name
    endpoint: Endpoint | None = None
    secret_name: SecretName | None = None
    timeout_seconds: float = Field(default=60, gt=0, le=3600)
    rate_limit_rpm: int | None = Field(default=None, gt=0)


class ProviderUpdate(Strict):
    name: Name | None = None
    endpoint: Endpoint | None = None
    secret_name: SecretName | None = None
    enabled: bool | None = None
    timeout_seconds: float | None = Field(default=None, gt=0, le=3600)
    rate_limit_rpm: int | None = Field(default=None, gt=0)


class ProviderRead(BaseModel):
    id: str
    type: str
    name: str
    endpoint: str | None
    secret_name: str | None
    has_secret: bool
    enabled: bool
    timeout_seconds: float
    rate_limit_rpm: int | None
    paid: bool
    created_at: datetime


class ConnectionResult(BaseModel):
    ok: bool
    message: str
    models_found: int | None = None
    latency_ms: int | None = None


class ModelCreate(Strict):
    model_id: Annotated[str, Field(min_length=1, max_length=200)]
    context_window: int | None = Field(default=None, gt=0)
    input_cost_per_mtok: float | None = Field(default=None, ge=0)
    output_cost_per_mtok: float | None = Field(default=None, ge=0)


class ModelUpdate(Strict):
    context_window: int | None = Field(default=None, gt=0)
    input_cost_per_mtok: float | None = Field(default=None, ge=0)
    output_cost_per_mtok: float | None = Field(default=None, ge=0)
    capability_overrides: dict[str, bool] | None = None
    defaults: dict[str, Any] | None = None


class ModelRead(BaseModel):
    id: str
    provider_id: str
    provider_name: str
    model_id: str
    context_window: int | None
    capabilities: dict[str, bool]
    capability_overrides: dict[str, bool]
    input_cost_per_mtok: float | None
    output_cost_per_mtok: float | None
    defaults: dict[str, Any]
    source: str
    last_test: dict[str, Any] | None
    parameter_fields: list[FieldSpec]


class ModelTest(Strict):
    prompt: str = Field(default="Reply with the single word: ready", max_length=2000)
    confirm_paid: bool = False


class ModelTestResult(BaseModel):
    ok: bool
    message: str
    text: str | None = None
    served_by: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    tested_at: datetime
