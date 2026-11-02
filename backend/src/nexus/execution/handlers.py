"""Implementations of the node types that run today. Agents, models and tools with side effects
are absent on purpose: an unregistered type is refused before a run starts."""

import asyncio
import json
from typing import Any

from langgraph.types import interrupt

from nexus.execution.context import MAX_SUB_WORKFLOW_DEPTH, NodeContext, NodeHandler, NodeResult
from nexus.execution.expressions import evaluate, render_template

UNAVAILABLE: dict[str, str] = {
    "Agents": "Milestone 5 (agent runtimes)",
    "Models": "Milestone 4 (model providers)",
    "Tools": "a later milestone, with permission enforcement",
    "Monitoring": "Milestone 7 (observability)",
}


async def _input(context: NodeContext) -> NodeResult:
    return NodeResult(output=context.workflow_input if context.input is None else context.input)


async def _output(context: NodeContext) -> NodeResult:
    return NodeResult(output=context.input)


async def _if_else(context: NodeContext) -> NodeResult:
    passed = bool(evaluate(context.config["expression"], context.scope))
    return NodeResult(output=context.input, ports=["true" if passed else "false"])


async def _switch(context: NodeContext) -> NodeResult:
    value = str(evaluate(context.config["value"], context.scope))
    for case in ("case_1", "case_2"):
        if case in context.config and value == context.config[case]:
            return NodeResult(output=context.input, ports=[case])
    return NodeResult(output=context.input, ports=["default"])


async def _parallel(context: NodeContext) -> NodeResult:
    return NodeResult(output=context.input)


async def _merge(context: NodeContext) -> NodeResult:
    values = context.inputs.get("in") or []
    strategy = context.config.get("strategy", "wait_all")
    if strategy == "first":
        return NodeResult(output=values[0] if values else None)
    if strategy == "concatenate":
        if all(isinstance(value, list) for value in values):
            return NodeResult(output=[item for value in values for item in value])
        return NodeResult(output="".join(str(value) for value in values))
    return NodeResult(output=values)


async def _delay(context: NodeContext) -> NodeResult:
    await asyncio.sleep(context.config["seconds"])
    return NodeResult(output=context.input)


async def _stop(context: NodeContext) -> NodeResult:
    return NodeResult(output=context.input, stop=context.config.get("status", "completed"))


async def _error_handler(context: NodeContext) -> NodeResult:
    return NodeResult(output=context.error)


async def _json_parser(context: NodeContext) -> NodeResult:
    return NodeResult(output=json.loads(context.input))


async def _data_transform(context: NodeContext) -> NodeResult:
    return NodeResult(output=render_template(context.config["template"], context.scope))


async def _variable(context: NodeContext) -> NodeResult:
    name = context.config["name"]
    if context.config.get("operation", "read") == "write":
        return NodeResult(output=context.input, variables={name: context.input})
    return NodeResult(output=context.variables.get(name))


async def _logger(context: NodeContext) -> NodeResult:
    text = context.input if isinstance(context.input, str) else json.dumps(context.input)
    await context.log(text, context.config.get("level", "info"))
    return NodeResult(output=context.input)


async def _human_approval(context: NodeContext) -> NodeResult:
    # A re-entered node replays earlier interrupts by position, so a pause released on this
    # node yields its own reply here first. Only a real decision may continue.
    reply: dict[str, Any] = {}
    while "decision" not in reply:
        reply = interrupt({"kind": "approval", "prompt": context.config["prompt"]})
    return NodeResult(output=context.input, ports=[reply["decision"]])


async def _sub_workflow(context: NodeContext) -> NodeResult:
    if context.depth >= MAX_SUB_WORKFLOW_DEPTH:
        raise ValueError(f"Sub-workflows are nested more than {MAX_SUB_WORKFLOW_DEPTH} levels")
    if context.run_workflow is None:
        raise ValueError("Sub-workflows are not available here")
    value = await context.run_workflow(context.config["workflow_id"], context.input, context.depth)
    return NodeResult(output=value)


async def _loop(context: NodeContext) -> NodeResult:
    state = dict(context.loop)
    iteration = state.get("iteration", 0) + 1
    repeated = context.inputs.get("repeat")
    current = repeated[-1] if repeated and iteration > 1 else context.input
    limit = context.config.get("max_iterations", 100)
    mode = context.config["mode"]

    if mode == "for_each":
        items = state.get("items")
        if items is None:
            if not isinstance(context.input, list):
                raise ValueError("For each needs a list as input")
            items = context.input
        results = state.get("results", [])
        if iteration > 1:
            results = [*results, current]
        if iteration > len(items):
            return NodeResult(output=results, ports=["done"], loop={})
        return NodeResult(
            output=items[iteration - 1],
            ports=["body"],
            loop={"iteration": iteration, "items": items, "results": results},
        )

    if iteration > limit:
        raise ValueError(f"Loop passed its limit of {limit} iterations")
    keep_going = (
        iteration <= context.config["count"]
        if mode == "count"
        else bool(evaluate(context.config["condition"], {**context.scope, "input": current}))
    )
    if keep_going:
        return NodeResult(output=current, ports=["body"], loop={"iteration": iteration})
    return NodeResult(output=current, ports=["done"], loop={})


BUILT_IN_HANDLERS: dict[str, NodeHandler] = {
    "core.input": _input,
    "core.output": _output,
    "core.if_else": _if_else,
    "core.switch": _switch,
    "core.parallel": _parallel,
    "core.merge": _merge,
    "core.delay": _delay,
    "core.stop": _stop,
    "core.error_handler": _error_handler,
    "core.json_parser": _json_parser,
    "core.data_transform": _data_transform,
    "core.variable": _variable,
    "core.logger": _logger,
    "core.human_approval": _human_approval,
    "core.sub_workflow": _sub_workflow,
    "core.loop": _loop,
}
