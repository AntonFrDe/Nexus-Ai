import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.errors import GraphBubbleUp
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from nexus.execution.context import (
    ExecutionHooks,
    NodeContext,
    NodeFailure,
    NodeHandler,
    NodeResult,
    WorkflowRunner,
)
from nexus.nodes.registry import NodeRegistry
from nexus.nodes.spec import NodeType
from nexus.workflows.schemas import WorkflowEdge, WorkflowGraph, WorkflowNode


def _merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {**left, **right}


def _latest(left: Any, right: Any) -> Any:
    return right if right is not None else left


class RunState(TypedDict):
    workflow_input: Any
    outputs: Annotated[dict[str, Any], _merge]
    routes: Annotated[dict[str, list[str]], _merge]
    variables: Annotated[dict[str, Any], _merge]
    loops: Annotated[dict[str, Any], _merge]
    errors: Annotated[dict[str, Any], _merge]
    stop: Annotated[str | None, _latest]


def initial_state(value: Any, variables: dict[str, Any]) -> RunState:
    return RunState(
        workflow_input=value,
        outputs={},
        routes={},
        variables=dict(variables),
        loops={},
        errors={},
        stop=None,
    )


@dataclass(frozen=True)
class Selection:
    """Which part of a workflow to run: `entry` limits the start, `only` limits the whole run."""

    entry: str | None = None
    only: bool = False


def _collect_inputs(
    state: RunState, incoming: list[WorkflowEdge], node_type: NodeType
) -> dict[str, Any]:
    collected: dict[str, list[Any]] = defaultdict(list)
    for edge in incoming:
        if edge.source_port in state["routes"].get(edge.source, []):
            collected[edge.target_port].append(state["outputs"].get(edge.source))
    multiple = {port.id for port in node_type.inputs if port.multiple}
    return {port: values if port in multiple else values[-1] for port, values in collected.items()}


def _primary(inputs: dict[str, Any], fallback: Any) -> Any:
    if "in" in inputs:
        return inputs["in"]
    return next(iter(inputs.values()), fallback)


class GraphCompiler:
    """Turns a validated workflow into a LangGraph graph. Node behavior comes only from
    registered handlers, so nothing in the document is ever executed as code."""

    def __init__(
        self,
        registry: NodeRegistry,
        handlers: dict[str, NodeHandler],
        run_workflow: WorkflowRunner | None = None,
    ) -> None:
        self.registry = registry
        self.handlers = handlers
        self.run_workflow = run_workflow

    def _node_function(
        self,
        node: WorkflowNode,
        node_type: NodeType,
        incoming: list[WorkflowEdge],
        hooks: ExecutionHooks,
        depth: int,
        entry_value: bool,
    ):
        handler = self.handlers[node.type]
        attempts = 1 + int(node.runtime.get("max_retries", 0))
        timeout = node.runtime.get("timeout_seconds") or None
        backoff = node.runtime.get("retry_backoff_seconds", 0)
        continue_on_error = node.runtime.get("on_error") == "continue"

        async def log(message: str, level: str) -> None:
            await hooks.log(node, message, level)

        async def run(state: RunState) -> dict[str, Any]:
            if hooks.pause_requested():
                await hooks.waiting(node)
                interrupt({"kind": "pause"})

            inputs = _collect_inputs(state, incoming, node_type)
            fallback = state["workflow_input"] if entry_value else None
            context = NodeContext(
                node=node,
                config=node.config,
                input=_primary(inputs, fallback),
                inputs=inputs,
                workflow_input=state["workflow_input"],
                variables=state["variables"],
                outputs=state["outputs"],
                loop=state["loops"].get(node.id, {}),
                error=next(iter(state["errors"].values()), None),
                depth=depth,
                log=log,
                run_workflow=self.run_workflow,
                allow_paid=hooks.allow_paid(),
            )
            for attempt in range(1, attempts + 1):
                await hooks.started(node, attempt, context.input)
                try:
                    async with asyncio.timeout(timeout):
                        result = await handler(context)
                except GraphBubbleUp:
                    await hooks.waiting(node)
                    raise
                except Exception as error:
                    text = str(error) or type(error).__name__
                    if isinstance(error, TimeoutError):
                        text = f"Timed out after {timeout} seconds"
                    final = attempt == attempts
                    await hooks.failed(node, attempt, text, final)
                    if not final:
                        await asyncio.sleep(backoff)
                        continue
                    if continue_on_error:
                        report = {"node_id": node.id, "error": text}
                        return {"errors": {node.id: report}, "routes": {node.id: []}}
                    raise NodeFailure(node.id, text) from error
                await hooks.finished(node, attempt, result.output, result.usage)
                return self._update(node, node_type, result)
            raise AssertionError("unreachable")

        return run

    @staticmethod
    def _update(node: WorkflowNode, node_type: NodeType, result: NodeResult) -> dict[str, Any]:
        ports = [port.id for port in node_type.outputs] if result.ports is None else result.ports
        update: dict[str, Any] = {
            "outputs": {node.id: result.output},
            "routes": {node.id: ports},
        }
        if result.variables:
            update["variables"] = result.variables
        if result.loop is not None:
            update["loops"] = {node.id: result.loop}
        if result.stop is not None:
            update["stop"] = result.stop
        return update

    def build(
        self,
        graph: WorkflowGraph,
        hooks: ExecutionHooks,
        checkpointer: BaseCheckpointSaver | None | bool,
        selection: Selection = Selection(),
        depth: int = 0,
    ) -> CompiledStateGraph:
        types = {node.type: self.registry.get(node.type) for node in graph.nodes}
        nodes = [node for node in graph.nodes if types[node.type].executable]
        if selection.only:
            nodes = [node for node in nodes if node.id == selection.entry]
        elif selection.entry:
            nodes = self._reachable(nodes, graph.edges, selection.entry)
        ids = {node.id for node in nodes}
        edges = [edge for edge in graph.edges if edge.source in ids and edge.target in ids]
        handlers_for_errors = [node for node in nodes if node.type == "core.error_handler"]

        incoming: dict[str, list[WorkflowEdge]] = defaultdict(list)
        outgoing: dict[str, list[WorkflowEdge]] = defaultdict(list)
        for edge in edges:
            incoming[edge.target].append(edge)
            outgoing[edge.source].append(edge)

        if selection.entry:
            entries = [selection.entry]
        else:
            entries = [
                node.id
                for node in nodes
                if not incoming[node.id] and node.type != "core.error_handler"
            ]

        builder = StateGraph(RunState)
        for node in nodes:
            function = self._node_function(
                node, types[node.type], incoming[node.id], hooks, depth, node.id in entries
            )
            # A deferred node waits until every running branch has finished.
            builder.add_node(node.id, function, defer=node.type == "core.merge")
        for entry in entries:
            builder.add_edge(START, entry)
        for node in nodes:
            self._add_router(builder, node, outgoing[node.id], handlers_for_errors)
        return builder.compile(checkpointer=checkpointer)

    @staticmethod
    def _reachable(
        nodes: list[WorkflowNode], edges: list[WorkflowEdge], entry: str
    ) -> list[WorkflowNode]:
        seen = {entry}
        frontier = [entry]
        while frontier:
            current = frontier.pop()
            for edge in edges:
                if edge.source == current and edge.target not in seen:
                    seen.add(edge.target)
                    frontier.append(edge.target)
        return [node for node in nodes if node.id in seen]

    @staticmethod
    def _add_router(
        builder: StateGraph,
        node: WorkflowNode,
        outgoing: list[WorkflowEdge],
        error_handlers: list[WorkflowNode],
    ) -> None:
        def route(state: RunState) -> list[str]:
            if state["stop"]:
                return [END]
            chosen = state["routes"].get(node.id, [])
            targets = {edge.target for edge in outgoing if edge.source_port in chosen}
            if node.id in state["errors"]:
                targets |= {
                    handler.id
                    for handler in error_handlers
                    if handler.config.get("scope") in (None, "", node.id)
                }
            return sorted(targets) or [END]

        possible = {edge.target for edge in outgoing} | {h.id for h in error_handlers}
        builder.add_conditional_edges(node.id, route, sorted(possible | {END}))
