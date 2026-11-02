from nexus.providers.service import ProviderRegistry
from nexus.runtimes.base import (
    AgentRequest,
    AgentResult,
    RuntimeAdapter,
    RuntimeCapabilities,
    UnsupportedCapability,
)


class NativeRuntime(RuntimeAdapter):
    """One model turn through the provider registry, so local models need no agent SDK."""

    id = "native"
    title = "Native"
    description = "Single model turn through the Model Registry. No tools yet."
    paid = False
    needs_secret = False
    concurrency = 4
    capabilities = RuntimeCapabilities(cancel=True)

    def __init__(self, registry: ProviderRegistry) -> None:
        self.registry = registry

    async def execute(self, request: AgentRequest, api_key: str | None) -> AgentResult:
        if request.tools or request.mcp_servers:
            raise UnsupportedCapability(self.id, "tools")
        answer = await self.registry.call(
            request.model,
            request.prompt,
            request.system_prompt,
            request.parameters,
            request.allow_paid,
        )
        return AgentResult(
            text=answer.text,
            runtime=self.id,
            model=answer.model,
            input_tokens=answer.input_tokens,
            output_tokens=answer.output_tokens,
        )
