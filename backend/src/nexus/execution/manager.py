import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.errors import GraphRecursionError
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from nexus.execution.agent_nodes import AgentServices
from nexus.execution.compiler import GraphCompiler, Selection, initial_state
from nexus.execution.context import NodeFailure, NodeHandler, NoHooks
from nexus.execution.handlers import UNAVAILABLE
from nexus.execution.states import ACTIVE, ExecutionStatus, NodeStatus
from nexus.execution.store import ExecutionStore
from nexus.nodes.registry import NodeRegistry
from nexus.workflows.schemas import Issue, WorkflowGraph, WorkflowNode
from nexus.workflows.validation import validate_workflow

RECURSION_LIMIT = 10_000
S = ExecutionStatus


class StartRefused(Exception):
    def __init__(self, issues: list[Issue]) -> None:
        super().__init__("The workflow cannot run")
        self.issues = issues


class ActionRefused(Exception):
    pass


def preflight(
    graph: WorkflowGraph,
    registry: NodeRegistry,
    handlers: dict[str, NodeHandler],
    selection: Selection = Selection(),
    agents: AgentServices | None = None,
    allow_paid: bool = False,
) -> list[Issue]:
    """Everything that stops a run from starting. Warnings never do."""
    partial = selection.entry is not None
    if partial and selection.entry not in {node.id for node in graph.nodes}:
        return [
            Issue(severity="error", code="unknown_entry", message="The chosen node does not exist")
        ]
    report = validate_workflow(graph, registry)
    included = _included(graph, selection)
    issues = [
        issue
        for issue in report.issues
        if issue.severity == "error"
        and not (partial and issue.code == "missing_required_input")
        and (issue.node_id is None or issue.node_id in included)
    ]
    for node in graph.nodes:
        node_type = registry.get(node.type)
        if node_type is None or not node_type.executable or node.id not in included:
            continue
        if node.type not in handlers:
            where = UNAVAILABLE.get(node_type.category, "a later milestone")
            issues.append(
                Issue(
                    severity="error",
                    code="not_executable",
                    message=f"{node.label or node_type.title} cannot run yet; arrives with {where}",
                    node_id=node.id,
                )
            )
        elif agents is not None:
            problem = agents.problem(node, allow_paid)
            if problem:
                issues.append(
                    Issue(
                        severity="error",
                        code="not_ready",
                        message=f"{node.label or node_type.title}: {problem}",
                        node_id=node.id,
                    )
                )
    return issues


def _included(graph: WorkflowGraph, selection: Selection) -> set[str]:
    if selection.only:
        return {selection.entry}
    if selection.entry:
        return {n.id for n in GraphCompiler._reachable(graph.nodes, graph.edges, selection.entry)}
    return {node.id for node in graph.nodes}


class _Hooks:
    """Connects one run's graph to its records and live events."""

    def __init__(self, manager: "ExecutionManager", execution_id: str, paid: bool) -> None:
        self.manager = manager
        self.execution_id = execution_id
        self.paid = paid

    def pause_requested(self) -> bool:
        return self.execution_id in self.manager.pause_requests

    def allow_paid(self) -> bool:
        return self.paid

    async def started(self, node: WorkflowNode, attempt: int, value: Any) -> None:
        await self.manager.store_call(
            "node_started", self.execution_id, node.id, node.type, attempt, value
        )
        await self.manager.emit(self.execution_id, "node_started", node.id, {"attempt": attempt})

    async def waiting(self, node: WorkflowNode) -> None:
        await self.manager.store_call("node_waiting", self.execution_id, node.id, node.type)
        await self.manager.emit(self.execution_id, "node_waiting", node.id, {})

    async def finished(
        self, node: WorkflowNode, attempt: int, output: Any, usage: dict[str, Any] | None
    ) -> None:
        await self.manager.store_call(
            "node_finished", self.execution_id, node.id, NodeStatus.COMPLETED, output, None, usage
        )
        payload: dict[str, Any] = {"attempt": attempt}
        if usage:
            payload["usage"] = usage
        await self.manager.emit(self.execution_id, "node_completed", node.id, payload)

    async def failed(self, node: WorkflowNode, attempt: int, error: str, final: bool) -> None:
        if final:
            await self.manager.store_call(
                "node_finished", self.execution_id, node.id, NodeStatus.FAILED, None, error
            )
        kind = "node_failed" if final else "node_retrying"
        await self.manager.emit(
            self.execution_id, kind, node.id, {"attempt": attempt, "error": error}
        )

    async def log(self, node: WorkflowNode, message: str, level: str) -> None:
        await self.manager.emit(
            self.execution_id, "log", node.id, {"message": message, "level": level}
        )


class ExecutionManager:
    """Runs workflows as background tasks, so the API never waits on a run."""

    def __init__(
        self,
        store: ExecutionStore,
        registry: NodeRegistry,
        handlers: dict[str, NodeHandler],
        checkpointer: BaseCheckpointSaver,
        load_workflow,
        max_concurrent: int = 4,
        agents: AgentServices | None = None,
    ) -> None:
        self.store = store
        self.registry = registry
        self.handlers = handlers
        self.agents = agents
        self.checkpointer = checkpointer
        self.load_workflow = load_workflow
        self.compiler = GraphCompiler(registry, handlers, self._run_child)
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.pause_requests: set[str] = set()
        self.locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.changed = asyncio.Condition()
        self.slots = asyncio.Semaphore(max_concurrent)
        self.shutting_down = False

    async def store_call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(getattr(self.store, method), *args, **kwargs)

    async def emit(
        self, execution_id: str, type_: str, node_id: str | None, payload: dict[str, Any]
    ) -> None:
        async with self.locks[execution_id]:
            await self.store_call("add_event", execution_id, type_, node_id, payload)
        async with self.changed:
            self.changed.notify_all()

    async def _set_status(self, execution_id: str, status: S, **fields: Any) -> None:
        await self.store_call("transition", execution_id, status, **fields)
        await self.emit(execution_id, "status", None, {"status": status.value})

    def _config(self, execution_id: str) -> dict[str, Any]:
        return {
            "configurable": {"thread_id": execution_id},
            "recursion_limit": RECURSION_LIMIT,
        }

    def _graph_for(self, execution) -> CompiledStateGraph:
        graph = WorkflowGraph.model_validate(execution.graph)
        selection = Selection(execution.entry_node, execution.mode == "node")
        hooks = _Hooks(self, execution.id, execution.allow_paid)
        return self.compiler.build(graph, hooks, self.checkpointer, selection)

    async def _run_child(self, workflow_id: str, value: Any, depth: int) -> Any:
        graph = await asyncio.to_thread(self.load_workflow, workflow_id)
        issues = preflight(graph, self.registry, self.handlers, agents=self.agents)
        if issues:
            raise ValueError(f"Sub-workflow cannot run: {issues[0].message}")
        if any(node.type == "core.human_approval" for node in graph.nodes):
            raise ValueError("Human approval is not supported inside a sub-workflow")
        compiled = self.compiler.build(graph, NoHooks(), False, depth=depth + 1)
        state = await compiled.ainvoke(
            initial_state(value, graph.variables), {"recursion_limit": RECURSION_LIMIT}
        )
        results = [
            state["outputs"][node.id]
            for node in graph.nodes
            if node.type == "core.output" and node.id in state["outputs"]
        ]
        return results[0] if len(results) == 1 else results

    async def start(
        self,
        graph: WorkflowGraph,
        *,
        workflow_id: str | None,
        workflow_name: str,
        workflow_version: int | None,
        value: Any,
        mode: str = "full",
        node_id: str | None = None,
        allow_paid: bool = False,
    ):
        if mode != "full" and node_id is None:
            raise ActionRefused("This mode needs a node")
        selection = Selection(node_id, mode == "node")
        issues = preflight(graph, self.registry, self.handlers, selection, self.agents, allow_paid)
        if issues:
            raise StartRefused(issues)
        execution = await self.store_call(
            "create",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            workflow_version=workflow_version,
            status=S.PENDING.value,
            mode=mode,
            entry_node=node_id,
            allow_paid=allow_paid,
            graph=graph.model_dump(mode="json"),
            input=value,
        )
        await self.emit(execution.id, "status", None, {"status": S.PENDING.value})
        self._launch(execution.id, initial_state(value, graph.variables), first=True)
        return execution

    def _launch(self, execution_id: str, payload: Any, *, first: bool = False, config=None) -> None:
        task = asyncio.create_task(self._drive(execution_id, payload, first, config))
        self.tasks[execution_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(execution_id, None))

    async def _drive(self, execution_id: str, payload: Any, first: bool, config) -> None:
        try:
            async with self.slots:
                if first:
                    await self._set_status(execution_id, S.VALIDATING)
                    await self._set_status(execution_id, S.RUNNING, started_at=datetime.now(UTC))
                execution = await self.store_call("get", execution_id)
                graph = self._graph_for(execution)
                run_config = config or self._config(execution_id)
                async for _ in graph.astream(payload, run_config, stream_mode="updates"):
                    pass
                await self._settle(execution_id, graph)
        except asyncio.CancelledError:
            await asyncio.shield(self._on_stop(execution_id))
        except (NodeFailure, GraphRecursionError, Exception) as error:
            await self._on_failure(execution_id, error)

    async def _on_stop(self, execution_id: str) -> None:
        if self.shutting_down:
            await self._set_status(
                execution_id, S.PAUSED, error="Stopped by a shutdown; resume to continue"
            )
            await self.store_call("close_open_nodes", execution_id, NodeStatus.PAUSED, None)
            return
        await self.store_call("close_open_nodes", execution_id, NodeStatus.FAILED, "Cancelled")
        await self._set_status(execution_id, S.CANCELLED, ended_at=datetime.now(UTC))

    async def _on_failure(self, execution_id: str, error: Exception) -> None:
        node_id = error.node_id if isinstance(error, NodeFailure) else None
        message = str(error) or type(error).__name__
        if isinstance(error, GraphRecursionError):
            message = f"Stopped after {RECURSION_LIMIT} steps"
        await self.store_call("close_open_nodes", execution_id, NodeStatus.FAILED, message)
        await self._finish(execution_id, S.FAILED, error=message, error_node=node_id)

    async def _pending(self, graph: CompiledStateGraph, execution_id: str) -> list[dict[str, Any]]:
        state = await graph.aget_state(self._config(execution_id))
        return [
            {"task": task.name, "interrupt_id": item.id, **item.value}
            for task in state.tasks
            for item in task.interrupts
        ]

    async def _settle(self, execution_id: str, graph: CompiledStateGraph) -> None:
        pending = await self._pending(graph, execution_id)
        if any(item["kind"] == "approval" for item in pending):
            self.pause_requests.discard(execution_id)
            await self._set_status(execution_id, S.WAITING_FOR_APPROVAL)
            return
        if pending:
            self.pause_requests.discard(execution_id)
            await self._set_status(execution_id, S.PAUSED)
            return
        state = await graph.aget_state(self._config(execution_id))
        if state.next:
            await self._finish(execution_id, S.FAILED, error="The run stopped unexpectedly")
            return
        await self._complete(execution_id, state.values)

    async def _complete(self, execution_id: str, values: dict[str, Any]) -> None:
        execution = await self.store_call("get", execution_id)
        workflow = WorkflowGraph.model_validate(execution.graph)
        outputs = values.get("outputs", {})
        named = {
            node.config.get("name", "result"): outputs[node.id]
            for node in workflow.nodes
            if node.type == "core.output" and node.id in outputs
        }
        recorded = {row.node_id for row in await self.store_call("nodes", execution_id)}
        included = _included(workflow, Selection(execution.entry_node, execution.mode == "node"))
        skipped = [
            (node.id, node.type)
            for node in workflow.nodes
            if node.id not in recorded
            and node.id in included
            and self.registry.get(node.type).executable
        ]
        await self.store_call("add_skipped", execution_id, skipped)
        for node_id, _ in skipped:
            await self.emit(execution_id, "node_skipped", node_id, {})
        if values.get("stop") == "failed":
            await self._finish(execution_id, S.FAILED, output=named, error="Stopped by a Stop node")
            return
        await self._finish(execution_id, S.COMPLETED, output=named, error=None, error_node=None)

    async def _finish(self, execution_id: str, status: S, **fields: Any) -> None:
        self.pause_requests.discard(execution_id)
        rows = await self.store_call("nodes", execution_id)
        execution = await self.store_call("get", execution_id)
        ended = datetime.now(UTC)
        started = execution.started_at
        metrics = {
            "nodes_run": sum(row.status == NodeStatus.COMPLETED for row in rows),
            "nodes_failed": sum(row.status == NodeStatus.FAILED for row in rows),
            "nodes_skipped": sum(row.status == NodeStatus.SKIPPED for row in rows),
            "models": sorted({row.usage["model"] for row in rows if row.usage}),
            "input_tokens": sum((row.usage or {}).get("input_tokens") or 0 for row in rows),
            "output_tokens": sum((row.usage or {}).get("output_tokens") or 0 for row in rows),
            "cost_usd": sum((row.usage or {}).get("cost_usd") or 0 for row in rows),
            "duration_ms": (
                int((ended - started.replace(tzinfo=UTC)).total_seconds() * 1000)
                if started
                else None
            ),
        }
        await self._set_status(execution_id, status, ended_at=ended, metrics=metrics, **fields)

    # Actions

    async def pending_approvals(self, execution) -> list[dict[str, Any]]:
        if execution.status != S.WAITING_FOR_APPROVAL:
            return []
        items = await self._pending(self._graph_for(execution), execution.id)
        return [item for item in items if item["kind"] == "approval"]

    async def pause(self, execution_id: str) -> None:
        execution = await self.store_call("get", execution_id)
        if execution.status not in ACTIVE:
            raise ActionRefused(f"Cannot pause a run that is {execution.status}")
        self.pause_requests.add(execution_id)
        await self.emit(execution_id, "pause_requested", None, {})

    async def _continue(self, execution, reply: dict[str, Any] | None) -> None:
        if execution.id in self.tasks:
            raise ActionRefused("The run is still active")
        graph = self._graph_for(execution)
        pending = await self._pending(graph, execution.id)
        state = await graph.aget_state(self._config(execution.id))
        if pending:
            answers = {
                item["interrupt_id"]: reply if item["kind"] == "approval" else {"go": True}
                for item in pending
            }
            payload: Any = Command(resume=answers)
        elif state.next:
            payload = None
        else:
            # Stopped before the first step: nothing is checkpointed yet.
            workflow = WorkflowGraph.model_validate(execution.graph)
            payload = initial_state(execution.input, workflow.variables)
        await self._set_status(execution.id, S.RUNNING, ended_at=None, error=None, error_node=None)
        self._launch(execution.id, payload)

    async def resume(self, execution_id: str) -> None:
        execution = await self.store_call("get", execution_id)
        if execution.status not in (S.PAUSED, S.FAILED, S.CANCELLED):
            raise ActionRefused(f"Cannot resume a run that is {execution.status}")
        self.pause_requests.discard(execution_id)
        await self._continue(execution, None)

    async def decide(self, execution_id: str, decision: str) -> None:
        execution = await self.store_call("get", execution_id)
        if execution.status != S.WAITING_FOR_APPROVAL:
            raise ActionRefused("This run is not waiting for approval")
        await self.emit(execution_id, "approval", None, {"decision": decision})
        await self._continue(execution, {"decision": decision})

    async def cancel(self, execution_id: str) -> None:
        execution = await self.store_call("get", execution_id)
        task = self.tasks.get(execution_id)
        if task is not None:
            task.cancel()
            return
        if execution.status not in (S.PAUSED, S.WAITING_FOR_APPROVAL, S.PENDING):
            raise ActionRefused(f"Cannot cancel a run that is {execution.status}")
        await self.store_call("close_open_nodes", execution_id, NodeStatus.FAILED, "Cancelled")
        await self._set_status(execution_id, S.CANCELLED, ended_at=datetime.now(UTC))

    async def checkpoints(self, execution_id: str) -> list[dict[str, Any]]:
        execution = await self.store_call("get", execution_id)
        graph = self._graph_for(execution)
        history = []
        async for snapshot in graph.aget_state_history(self._config(execution_id)):
            history.append(
                {
                    "checkpoint_id": snapshot.config["configurable"]["checkpoint_id"],
                    "next": list(snapshot.next),
                    "created_at": snapshot.created_at,
                }
            )
        return history

    async def restore(self, execution_id: str, checkpoint_id: str) -> None:
        """Continues from an earlier checkpoint, re-running everything after it."""
        execution = await self.store_call("get", execution_id)
        if execution_id in self.tasks or execution.status not in (
            S.PAUSED,
            S.FAILED,
            S.CANCELLED,
            S.COMPLETED,
        ):
            raise ActionRefused(f"Cannot restore a run that is {execution.status}")
        known = {item["checkpoint_id"] for item in await self.checkpoints(execution_id)}
        if checkpoint_id not in known:
            raise ActionRefused("Unknown checkpoint")
        config = self._config(execution_id)
        config["configurable"]["checkpoint_id"] = checkpoint_id
        await self._set_status(execution_id, S.RUNNING, ended_at=None, error=None, error_node=None)
        self._launch(execution_id, None, config=config)

    async def recover(self) -> None:
        """After a restart, runs that were live hold only a checkpoint. They wait to be resumed."""
        for execution in await self.store_call("with_status", ACTIVE):
            await self.store_call("close_open_nodes", execution.id, NodeStatus.PAUSED, None)
            await self._set_status(
                execution.id, S.PAUSED, error="Interrupted by a restart; resume to continue"
            )

    async def shutdown(self) -> None:
        self.shutting_down = True
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
