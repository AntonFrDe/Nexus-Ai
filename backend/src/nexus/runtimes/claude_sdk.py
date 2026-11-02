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
)


def build_options(request: AgentRequest, api_key: str, working_directory: str) -> dict[str, Any]:
    """Isolates the child process from this machine's Claude Code setup. It inherits the parent's
    environment, so the OAuth token is blanked: without that, a missing or rejected key could
    fall back to a personal subscription login without anyone noticing."""
    options: dict[str, Any] = {
        "model": request.model,
        "system_prompt": request.system_prompt or None,
        "cwd": working_directory,
        "env": {"ANTHROPIC_API_KEY": api_key, "CLAUDE_CODE_OAUTH_TOKEN": ""},
        # No user or project settings: their hooks and permissions must not apply here.
        "setting_sources": [],
        "tools": list(request.tools),
        "permission_mode": "default",
    }
    if request.max_turns is not None:
        options["max_turns"] = request.max_turns
    if request.max_budget_usd is not None:
        options["max_budget_usd"] = request.max_budget_usd
    return options


class ClaudeAgentRuntime(RuntimeAdapter):
    id = "claude-agent-sdk"
    title = "Claude Agent SDK"
    description = "Claude agents, billed to a Claude Console API key. Subscriptions are not used."
    concurrency = 1
    capabilities = RuntimeCapabilities(interruptible=True, tools=True)

    async def health_check(self) -> RuntimeHealth:
        if importlib.util.find_spec("claude_agent_sdk") is None:
            return RuntimeHealth(ready=False, message="Install with: uv sync --extra agents")
        return RuntimeHealth(ready=True, message="SDK installed")

    async def execute(self, request: AgentRequest, api_key: str | None) -> AgentResult:
        if not api_key:
            raise RuntimeError_("The Claude Agent SDK runtime needs an API key")
        from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, query

        result = None
        model = request.model
        with tempfile.TemporaryDirectory(prefix="nexus-claude-") as directory:
            options = ClaudeAgentOptions(**build_options(request, api_key, directory))
            async for message in query(prompt=request.prompt, options=options):
                if isinstance(message, AssistantMessage):
                    model = message.model or model
                elif isinstance(message, ResultMessage):
                    result = message
        if result is None:
            raise RuntimeError_("The SDK ended without a result")
        if result.is_error:
            raise RuntimeError_(result.result or result.subtype)
        usage = result.usage or {}
        return AgentResult(
            text=result.result or "",
            runtime=self.id,
            model=model,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            cost_usd=result.total_cost_usd,
            session_id=result.session_id,
        )
