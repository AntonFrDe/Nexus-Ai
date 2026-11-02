from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from nexus.workflows.schemas import WorkflowNode

MAX_SUB_WORKFLOW_DEPTH = 5


class NodeFailure(Exception):
    def __init__(self, node_id: str, message: str) -> None:
        super().__init__(message)
        self.node_id = node_id


class WorkflowRunner(Protocol):
    async def __call__(self, workflow_id: str, value: Any, depth: int) -> Any: ...


@dataclass
class NodeContext:
    node: WorkflowNode
    config: dict[str, Any]
    input: Any
    inputs: dict[str, Any]
    workflow_input: Any
    variables: dict[str, Any]
    outputs: dict[str, Any]
    loop: dict[str, Any]
    error: dict[str, Any] | None
    depth: int
    log: Callable[[str, str], Awaitable[None]]
    run_workflow: WorkflowRunner | None

    @property
    def scope(self) -> dict[str, Any]:
        return {
            "input": self.input,
            "workflow": self.workflow_input,
            "variables": self.variables,
            "outputs": self.outputs,
        }


@dataclass
class NodeResult:
    output: Any = None
    # Output ports to follow. None follows every port.
    ports: list[str] | None = None
    variables: dict[str, Any] = field(default_factory=dict)
    loop: dict[str, Any] | None = None
    stop: str | None = None


NodeHandler = Callable[[NodeContext], Awaitable[NodeResult]]


class ExecutionHooks(Protocol):
    def pause_requested(self) -> bool: ...
    async def started(self, node: WorkflowNode, attempt: int, value: Any) -> None: ...
    async def waiting(self, node: WorkflowNode) -> None: ...
    async def finished(self, node: WorkflowNode, attempt: int, output: Any) -> None: ...
    async def failed(self, node: WorkflowNode, attempt: int, error: str, final: bool) -> None: ...
    async def log(self, node: WorkflowNode, message: str, level: str) -> None: ...


class NoHooks:
    """Sub-workflows report as one step of their parent."""

    def pause_requested(self) -> bool:
        return False

    async def started(self, node: WorkflowNode, attempt: int, value: Any) -> None:
        pass

    async def waiting(self, node: WorkflowNode) -> None:
        pass

    async def finished(self, node: WorkflowNode, attempt: int, output: Any) -> None:
        pass

    async def failed(self, node: WorkflowNode, attempt: int, error: str, final: bool) -> None:
        pass

    async def log(self, node: WorkflowNode, message: str, level: str) -> None:
        pass
