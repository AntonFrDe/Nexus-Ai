import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from nexus.providers.capabilities import capabilities_from_parameters
from nexus.providers.catalog import ProviderType

ANTHROPIC_VERSION = "2023-06-01"


@dataclass(frozen=True)
class Connection:
    """Everything an adapter needs for one call. The key lives only as long as the call."""

    provider_type: ProviderType
    endpoint: str | None
    api_key: str | None
    timeout: float

    def scrub(self, text: str) -> str:
        return text.replace(self.api_key, "[redacted]") if self.api_key else text


@dataclass
class ModelFacts:
    model_id: str
    context_window: int | None = None
    capabilities: dict[str, bool] = field(default_factory=dict)
    input_cost_per_mtok: float | None = None
    output_cost_per_mtok: float | None = None


@dataclass
class Completion:
    text: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int


class ProviderError(Exception):
    pass


class ProviderAdapter(Protocol):
    async def list_models(self, connection: Connection) -> list[str]: ...
    async def describe(self, connection: Connection, model_id: str) -> ModelFacts: ...
    async def complete(
        self, connection: Connection, model_id: str, prompt: str, parameters: dict[str, Any]
    ) -> Completion: ...


def _litellm():
    # Imported late: it is slow to load, and without this flag it fetches a price table online.
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    import litellm

    litellm.suppress_debug_info = True
    litellm.drop_params = False
    return litellm


def _per_million(cost: float | None) -> float | None:
    return None if cost is None else round(cost * 1_000_000, 6)


class LiteLLMAdapter:
    """Discovery uses each provider's HTTP API; completions go through LiteLLM."""

    async def list_models(self, connection: Connection) -> list[str]:
        style = connection.provider_type.discovery
        if style == "manual":
            raise ProviderError("This provider has no model listing; add models by hand")
        if not connection.endpoint:
            raise ProviderError("This provider needs an endpoint")
        base = connection.endpoint.rstrip("/")
        headers: dict[str, str] = {}
        if style == "ollama":
            url = f"{base}/api/tags"
        elif style == "anthropic":
            url = f"{base}/v1/models"
            headers = {"anthropic-version": ANTHROPIC_VERSION}
            if connection.api_key:
                headers["x-api-key"] = connection.api_key
        else:
            url = f"{base}/models"
            if connection.api_key:
                headers["Authorization"] = f"Bearer {connection.api_key}"
        try:
            async with httpx.AsyncClient(timeout=connection.timeout) as client:
                response = await client.get(url, headers=headers)
        except httpx.HTTPError as error:
            raise ProviderError(connection.scrub(f"Cannot reach {base}: {error}")) from error
        if response.status_code >= 400:
            raise ProviderError(f"{base} answered {response.status_code}")
        try:
            body = response.json()
            if style == "ollama":
                return [item["name"] for item in body["models"]]
            return [item["id"] for item in body["data"]]
        except (ValueError, KeyError, TypeError) as error:
            raise ProviderError(f"{base} sent an unexpected answer") from error

    def _qualified(self, connection: Connection, model_id: str) -> str:
        return f"{connection.provider_type.litellm_prefix}/{model_id}"

    def _describe(self, connection: Connection, model_id: str) -> ModelFacts:
        litellm = _litellm()
        name = self._qualified(connection, model_id)
        parameters = litellm.get_supported_openai_params(model=name) or []
        facts = ModelFacts(
            model_id=model_id,
            capabilities=capabilities_from_parameters(parameters, connection.provider_type.top_k),
        )
        try:
            info = litellm.get_model_info(name)
        except Exception:
            # Unknown to LiteLLM's tables: context and pricing stay unset rather than guessed.
            return facts
        facts.context_window = info.get("max_input_tokens")
        if not connection.provider_type.local:
            facts.input_cost_per_mtok = _per_million(info.get("input_cost_per_token"))
            facts.output_cost_per_mtok = _per_million(info.get("output_cost_per_token"))
        return facts

    async def describe(self, connection: Connection, model_id: str) -> ModelFacts:
        return await asyncio.to_thread(self._describe, connection, model_id)

    async def complete(
        self, connection: Connection, model_id: str, prompt: str, parameters: dict[str, Any]
    ) -> Completion:
        litellm = await asyncio.to_thread(_litellm)
        started = time.perf_counter()
        options: dict[str, Any] = {
            "model": self._qualified(connection, model_id),
            "messages": [{"role": "user", "content": prompt}],
            "timeout": connection.timeout,
            "num_retries": 0,
            **parameters,
        }
        if connection.endpoint:
            options["api_base"] = connection.endpoint
        # LiteLLM requires a value for OpenAI-style servers, even those without auth.
        options["api_key"] = connection.api_key or "not-needed"
        try:
            response = await litellm.acompletion(**options)
        except Exception as error:
            raise ProviderError(connection.scrub(str(error))) from error
        usage = getattr(response, "usage", None)
        return Completion(
            text=response.choices[0].message.content or "",
            model=response.model or model_id,
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
