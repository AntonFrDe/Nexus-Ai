from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


class RuntimeCapabilities(BaseModel):
    """What a runtime really does. Anything false is refused, never simulated."""

    streaming: bool = False
    pause: bool = False
    cancel: bool = False
    session_restore: bool = False
    tools: bool = False
    mcp: bool = False
    structured_output: bool = False


class RuntimeHealth(BaseModel):
    ready: bool
    message: str


class UnsupportedCapability(Exception):
    def __init__(self, runtime: str, capability: str) -> None:
        super().__init__(f"The {runtime} runtime does not support {capability}")
        self.runtime = runtime
        self.capability = capability


class RuntimeError_(Exception):
    pass


@dataclass
class AgentRequest:
    prompt: str
    model: str
    system_prompt: str = ""
    tools: list[str] = field(default_factory=list)
    mcp_servers: list[dict[str, Any]] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    max_turns: int | None = None
    max_budget_usd: float | None = None
    session_id: str | None = None
    allow_paid: bool = False


@dataclass
class AgentResult:
    text: str
    runtime: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    session_id: str | None = None

    def usage(self) -> dict[str, Any]:
        return {
            "runtime": self.runtime,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "session_id": self.session_id,
        }


class RuntimeAdapter:
    """The common contract. Each operation a runtime lacks stays refused by these defaults."""

    id: str
    title: str
    description: str
    # Calls use a billed credential, so a run must allow them explicitly.
    paid: bool = True
    needs_secret: bool = True
    # Sessions that may run at once on this runtime.
    concurrency: int = 1
    capabilities = RuntimeCapabilities()

    async def initialize(self) -> None:
        pass

    async def execute(self, request: AgentRequest, api_key: str | None) -> AgentResult:
        raise UnsupportedCapability(self.id, "execution")

    async def stream(self, request: AgentRequest, api_key: str | None):
        raise UnsupportedCapability(self.id, "streaming")

    async def pause(self, session_id: str) -> None:
        raise UnsupportedCapability(self.id, "pause")

    async def resume(self, session_id: str) -> None:
        raise UnsupportedCapability(self.id, "resume")

    async def cancel(self, session_id: str) -> None:
        raise UnsupportedCapability(self.id, "cancel")

    async def get_session(self, session_id: str) -> dict[str, Any]:
        raise UnsupportedCapability(self.id, "session inspection")

    async def restore_session(self, session_id: str) -> None:
        raise UnsupportedCapability(self.id, "session restoration")

    async def health_check(self) -> RuntimeHealth:
        return RuntimeHealth(ready=True, message="Available")
