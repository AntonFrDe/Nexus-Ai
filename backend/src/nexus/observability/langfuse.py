import base64
import hashlib
import json
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session, sessionmaker

from nexus.secrets.service import SecretService, SecretUnavailable
from nexus.settings_store.models import AppSetting

SETTING_KEY = "langfuse"
TIMEOUT_SECONDS = 15


class LangfuseConfig(BaseModel):
    """Off by default: enabling it sends run data to the configured host."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    host: str = Field(default="https://cloud.langfuse.com", pattern=r"^https?://", max_length=300)
    public_key: str = Field(default="", max_length=200)
    secret_name: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.\-]{1,120}$")
    # Metadata only unless the user chooses to send prompts and outputs.
    include_content: bool = False


def _nanos(moment: datetime | None) -> str:
    return str(int(moment.timestamp() * 1_000_000_000)) if moment else "0"


def _hex_id(seed: str, length: int) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:length]


def _attribute(key: str, value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    return {"key": key, "value": {"stringValue": str(value)}}


def _attributes(values: dict[str, Any]) -> list[dict[str, Any]]:
    return [_attribute(key, value) for key, value in values.items() if value is not None]


def build_trace(execution, rows, include_content: bool) -> dict[str, Any]:
    """An OTLP/HTTP JSON document: one root span for the run and one child per node attempt."""
    trace_id = _hex_id(execution.id, 32)
    root_id = _hex_id(f"{execution.id}:root", 16)
    root = {
        "traceId": trace_id,
        "spanId": root_id,
        "name": execution.workflow_name,
        "kind": 1,
        "startTimeUnixNano": _nanos(execution.started_at or execution.created_at),
        "endTimeUnixNano": _nanos(execution.ended_at),
        "attributes": _attributes(
            {
                "langfuse.trace.name": execution.workflow_name,
                "nexus.execution.id": execution.id,
                "nexus.execution.status": execution.status,
            }
        ),
        "status": {"code": 2 if execution.status == "FAILED" else 1},
    }
    spans = [root]
    for row in rows:
        usage = row.usage or {}
        attributes: dict[str, Any] = {
            "nexus.node.id": row.node_id,
            "nexus.node.type": row.node_type,
            "nexus.node.status": row.status,
            "gen_ai.request.model": usage.get("model"),
            "gen_ai.usage.input_tokens": usage.get("input_tokens"),
            "gen_ai.usage.output_tokens": usage.get("output_tokens"),
            "gen_ai.usage.cost": usage.get("cost_usd"),
        }
        if usage:
            attributes["langfuse.observation.type"] = "generation"
        if include_content:
            attributes["langfuse.observation.input"] = json.dumps(row.input)
            attributes["langfuse.observation.output"] = json.dumps(row.output)
        spans.append(
            {
                "traceId": trace_id,
                "spanId": _hex_id(row.id, 16),
                "parentSpanId": root_id,
                "name": row.node_id,
                "kind": 1,
                "startTimeUnixNano": _nanos(row.started_at),
                "endTimeUnixNano": _nanos(row.ended_at or row.started_at),
                "attributes": _attributes(attributes),
                "status": {"code": 2 if row.status == "FAILED" else 1},
            }
        )
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": _attributes({"service.name": "nexus"})},
                "scopeSpans": [{"scope": {"name": "nexus"}, "spans": spans}],
            }
        ]
    }


class LangfuseExporter:
    def __init__(self, factory: sessionmaker[Session], secrets: SecretService) -> None:
        self.factory = factory
        self.secrets = secrets

    def config(self) -> LangfuseConfig:
        with self.factory() as session:
            row = session.get(AppSetting, SETTING_KEY)
            return LangfuseConfig.model_validate(row.value) if row else LangfuseConfig()

    def save(self, config: LangfuseConfig) -> LangfuseConfig:
        with self.factory() as session, session.begin():
            session.merge(AppSetting(key=SETTING_KEY, value=config.model_dump()))
        return config

    def _headers(self, config: LangfuseConfig) -> tuple[dict[str, str], str]:
        if not config.public_key or not config.secret_name:
            raise SecretUnavailable("Langfuse needs a public key and a secret")
        secret = self.secrets.resolve(config.secret_name)
        token = base64.b64encode(f"{config.public_key}:{secret}".encode()).decode()
        return {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "x-langfuse-ingestion-version": "4",
        }, secret

    async def check(self, config: LangfuseConfig) -> str | None:
        """Returns what went wrong, or None when the keys are accepted."""
        try:
            headers, secret = self._headers(config)
        except SecretUnavailable as error:
            return str(error)
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.get(
                    f"{config.host.rstrip('/')}/api/public/projects", headers=headers
                )
        except httpx.HTTPError as error:
            return str(error).replace(secret, "[redacted]")
        return (
            None if response.status_code < 400 else f"{config.host} answered {response.status_code}"
        )

    async def export(self, execution, rows) -> None:
        """Raises on failure so the caller can record it; it never changes the run's own result."""
        config = self.config()
        if not config.enabled:
            return
        headers, secret = self._headers(config)
        body = build_trace(execution, rows, config.include_content)
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{config.host.rstrip('/')}/api/public/otel/v1/traces",
                    headers=headers,
                    json=body,
                )
        except httpx.HTTPError as error:
            raise RuntimeError(str(error).replace(secret, "[redacted]")) from None
        if response.status_code >= 400:
            raise RuntimeError(f"Langfuse answered {response.status_code}")
