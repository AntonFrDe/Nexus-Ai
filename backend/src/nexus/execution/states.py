from enum import StrEnum


class ExecutionStatus(StrEnum):
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NodeStatus(StrEnum):
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


_S = ExecutionStatus
TRANSITIONS: dict[ExecutionStatus, set[ExecutionStatus]] = {
    _S.PENDING: {_S.VALIDATING, _S.CANCELLED, _S.PAUSED},
    _S.VALIDATING: {_S.RUNNING, _S.FAILED, _S.CANCELLED, _S.PAUSED},
    _S.RUNNING: {_S.PAUSED, _S.WAITING_FOR_APPROVAL, _S.COMPLETED, _S.FAILED, _S.CANCELLED},
    _S.PAUSED: {_S.RUNNING, _S.WAITING_FOR_APPROVAL, _S.CANCELLED, _S.FAILED},
    _S.WAITING_FOR_APPROVAL: {_S.RUNNING, _S.PAUSED, _S.CANCELLED, _S.FAILED},
    # Terminal, except that a failure or completed run can resume from a checkpoint.
    _S.FAILED: {_S.RUNNING},
    _S.CANCELLED: {_S.RUNNING},
    _S.COMPLETED: {_S.RUNNING},
}
TERMINAL = {_S.COMPLETED, _S.FAILED, _S.CANCELLED}
ACTIVE = {_S.PENDING, _S.VALIDATING, _S.RUNNING}


class InvalidTransition(Exception):
    def __init__(self, current: ExecutionStatus, target: ExecutionStatus) -> None:
        super().__init__(f"Cannot go from {current} to {target}")


def check_transition(current: ExecutionStatus, target: ExecutionStatus) -> None:
    if target not in TRANSITIONS[current]:
        raise InvalidTransition(current, target)
