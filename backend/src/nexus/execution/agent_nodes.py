"""Node types that reach models and agents. They only run through registered services."""

import json
from dataclasses import dataclass
from typing import Any

from nexus.agents.service import AgentNotFound, AgentStore
from nexus.execution.context import NodeContext, NodeHandler, NodeResult
from nexus.providers.service import PaidCallRefused, ProviderRegistry
from nexus.runtimes.base import AgentRequest
from nexus.runtimes.service import RuntimeRegistry
from nexus.workflows.schemas import WorkflowNode


def _prompt(value: Any) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else json.dumps(value)


@dataclass
class AgentServices:
    providers: ProviderRegistry
    runtimes: RuntimeRegistry
    agents: AgentStore

    def problem(self, node: WorkflowNode) -> str | None:
        """Checked before a run, so a missing model stops it at the start."""
        if node.type == "core.llm_agent":
            return self.providers.reference_problem(node.config.get("model", ""))
        if node.type == "core.model_selector":
            return self.providers.reference_problem(node.config.get("model", ""))
        if node.type == "core.model_fallback":
            for reference in node.config.get("models", []):
                problem = self.providers.reference_problem(reference)
                if problem:
                    return problem
        if node.type == "core.custom_agent":
            return self._agent_problem(node.config.get("agent_id", ""))
        return None

    def _agent_problem(self, agent_id: str) -> str | None:
        try:
            agent = self.agents.get(agent_id)
        except AgentNotFound:
            return f"Agent {agent_id} does not exist"
        fields = self.agents.problems(agent.definition)
        if fields:
            return f"Agent {agent.name}: {fields[0][1]}"
        runtime = agent.definition["runtime"]
        problem = self.runtimes.problem(runtime)
        if problem:
            return problem
        if runtime == "native":
            return self.providers.reference_problem(agent.definition["model"])
        return None

    async def _attempts(
        self, context: NodeContext, references: list[str], make_request
    ) -> NodeResult:
        """Tries each model in order. The usage record names the one that really answered."""
        failures: list[str] = []
        for reference in references:
            try:
                result = await self.runtimes.run("native", make_request(reference))
            except PaidCallRefused:
                raise
            except Exception as error:
                failures.append(f"{reference}: {error}")
                await context.log(f"{reference} failed: {error}", "warning")
                continue
            usage = {**result.usage(), "requested": reference, "fallbacks_used": len(failures)}
            return NodeResult(output=result.text, usage=usage)
        raise ValueError("; ".join(failures) or "No model to call")

    async def llm_agent(self, context: NodeContext) -> NodeResult:
        chosen = context.inputs.get("model")
        references = (
            chosen["models"]
            if isinstance(chosen, dict) and "models" in chosen
            else [context.config["model"]]
        )
        config = context.config
        parameters = {
            name: config[name] for name in ("temperature", "max_tokens") if name in config
        }

        def request(reference: str) -> AgentRequest:
            return AgentRequest(
                prompt=_prompt(context.input),
                model=reference,
                system_prompt=config.get("system_prompt", ""),
                parameters=parameters,
                allow_paid=context.allow_paid,
            )

        return await self._attempts(context, references, request)

    async def model_selector(self, context: NodeContext) -> NodeResult:
        return NodeResult(output={"models": [context.config["model"]]})

    async def model_fallback(self, context: NodeContext) -> NodeResult:
        return NodeResult(output={"models": context.config["models"]})

    async def custom_agent(self, context: NodeContext) -> NodeResult:
        agent = self.agents.get(context.config["agent_id"])
        definition = agent.definition
        result = await self.runtimes.run(
            definition["runtime"],
            AgentRequest(
                prompt=_prompt(context.input),
                model=definition["model"],
                system_prompt=definition.get("system_prompt", ""),
                tools=definition.get("tools", []),
                max_turns=definition.get("max_turns"),
                max_budget_usd=definition.get("max_budget_usd"),
                allow_paid=context.allow_paid,
            ),
        )
        usage = {**result.usage(), "agent": agent.name, "agent_version": agent.version}
        return NodeResult(output=result.text, usage=usage)

    def handlers(self) -> dict[str, NodeHandler]:
        return {
            "core.llm_agent": self.llm_agent,
            "core.custom_agent": self.custom_agent,
            "core.model_selector": self.model_selector,
            "core.model_fallback": self.model_fallback,
        }
