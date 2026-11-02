import importlib.util
import tempfile
from typing import Any

from nexus.runtimes.base import (
    AgentRequest,
    AgentResult,
    RuntimeAdapter,
    RuntimeCapabilities,
    RuntimeError_,
    RuntimeHealth,
    UnsupportedCapability,
)


def build_config(request: AgentRequest, api_key: str, working_directory: str) -> dict[str, Any]:
    """Left at the SDK's read-only default: write access has to be granted deliberately."""
    config: dict[str, Any] = {"api_key": api_key, "workspaces": [working_directory]}
    if request.model:
        config["model"] = request.model
    if request.system_prompt:
        config["system_instructions"] = request.system_prompt
    return config


class AntigravityRuntime(RuntimeAdapter):
    """Uses the official Python SDK with a Gemini API key. It never drives the Antigravity IDE."""

    id = "antigravity-sdk"
    title = "Antigravity SDK"
    description = "Google agents, billed to a Gemini API key. Subscriptions are not used."
    concurrency = 1
    capabilities = RuntimeCapabilities(streaming=False, cancel=True)

    async def health_check(self) -> RuntimeHealth:
        if importlib.util.find_spec("google.antigravity") is None:
            return RuntimeHealth(ready=False, message="Install with: uv sync --extra agents")
        return RuntimeHealth(ready=True, message="SDK installed")

    async def execute(self, request: AgentRequest, api_key: str | None) -> AgentResult:
        if not api_key:
            raise RuntimeError_("The Antigravity runtime needs a Gemini API key")
        if request.tools or request.mcp_servers:
            raise UnsupportedCapability(self.id, "custom tools")
        from google.antigravity import Agent, LocalAgentConfig

        with tempfile.TemporaryDirectory(prefix="nexus-antigravity-") as directory:
            config = LocalAgentConfig(**build_config(request, api_key, directory))
            async with Agent(config) as agent:
                response = await agent.chat(request.prompt)
                text = await response.text()
        return AgentResult(text=text, runtime=self.id, model=request.model)
