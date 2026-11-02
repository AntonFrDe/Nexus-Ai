from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from nexus.execution.models import Execution, ExecutionEvent, NodeExecution
from nexus.execution.states import ExecutionStatus, NodeStatus, check_transition


class ExecutionNotFound(Exception):
    pass


class ExecutionStore:
    """All execution persistence. Other databases can replace this class alone."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self.factory = factory

    def create(self, **fields: Any) -> Execution:
        with self.factory() as session, session.begin():
            execution = Execution(**fields)
            session.add(execution)
            session.flush()
            session.expunge(execution)
            return execution

    def get(self, execution_id: str) -> Execution:
        with self.factory() as session:
            execution = session.get(Execution, execution_id)
            if execution is None:
                raise ExecutionNotFound(execution_id)
            session.expunge(execution)
            return execution

    def recent(self, workflow_id: str | None, limit: int) -> list[Execution]:
        query = select(Execution).order_by(Execution.created_at.desc()).limit(limit)
        if workflow_id:
            query = query.where(Execution.workflow_id == workflow_id)
        with self.factory() as session:
            rows = list(session.scalars(query))
            session.expunge_all()
            return rows

    def with_status(self, statuses: set[ExecutionStatus]) -> list[Execution]:
        query = select(Execution).where(Execution.status.in_([s.value for s in statuses]))
        with self.factory() as session:
            rows = list(session.scalars(query))
            session.expunge_all()
            return rows

    def transition(self, execution_id: str, target: ExecutionStatus, **fields: Any) -> None:
        with self.factory() as session, session.begin():
            execution = session.get(Execution, execution_id)
            if execution is None:
                raise ExecutionNotFound(execution_id)
            check_transition(ExecutionStatus(execution.status), target)
            execution.status = target.value
            for name, value in fields.items():
                setattr(execution, name, value)

    def nodes(self, execution_id: str) -> list[NodeExecution]:
        query = (
            select(NodeExecution)
            .where(NodeExecution.execution_id == execution_id)
            .order_by(NodeExecution.started_at)
        )
        with self.factory() as session:
            rows = list(session.scalars(query))
            session.expunge_all()
            return rows

    def _open_row(self, session: Session, execution_id: str, node_id: str) -> NodeExecution | None:
        query = select(NodeExecution).where(
            NodeExecution.execution_id == execution_id,
            NodeExecution.node_id == node_id,
            NodeExecution.status.in_([NodeStatus.RUNNING, NodeStatus.WAITING, NodeStatus.PAUSED]),
        )
        return session.scalars(query).first()

    def node_started(
        self, execution_id: str, node_id: str, node_type: str, attempt: int, value: Any
    ) -> None:
        with self.factory() as session, session.begin():
            # LangGraph re-enters an interrupted node, which continues the same record.
            row = self._open_row(session, execution_id, node_id)
            if row is None:
                session.add(
                    NodeExecution(
                        execution_id=execution_id,
                        node_id=node_id,
                        node_type=node_type,
                        attempt=attempt,
                        status=NodeStatus.RUNNING,
                        input=value,
                    )
                )
            else:
                row.status = NodeStatus.RUNNING
                row.attempt = attempt

    def node_finished(
        self,
        execution_id: str,
        node_id: str,
        status: NodeStatus,
        output: Any = None,
        error: str | None = None,
        usage: dict[str, Any] | None = None,
    ) -> None:
        with self.factory() as session, session.begin():
            row = self._open_row(session, execution_id, node_id)
            if row is None:
                return
            row.status = status
            row.output = output
            row.error = error
            row.usage = usage
            if status in (NodeStatus.COMPLETED, NodeStatus.FAILED):
                row.ended_at = datetime.now(UTC)

    def node_waiting(self, execution_id: str, node_id: str, node_type: str) -> None:
        with self.factory() as session, session.begin():
            row = self._open_row(session, execution_id, node_id)
            if row is None:
                session.add(
                    NodeExecution(
                        execution_id=execution_id,
                        node_id=node_id,
                        node_type=node_type,
                        status=NodeStatus.WAITING,
                    )
                )
            else:
                row.status = NodeStatus.WAITING

    def close_open_nodes(self, execution_id: str, status: NodeStatus, error: str | None) -> None:
        query = select(NodeExecution).where(
            NodeExecution.execution_id == execution_id,
            NodeExecution.status.in_([NodeStatus.RUNNING, NodeStatus.WAITING, NodeStatus.PAUSED]),
        )
        with self.factory() as session, session.begin():
            for row in session.scalars(query):
                row.status = status
                row.error = error
                row.ended_at = datetime.now(UTC)

    def add_skipped(self, execution_id: str, nodes: list[tuple[str, str]]) -> None:
        now = datetime.now(UTC)
        with self.factory() as session, session.begin():
            for node_id, node_type in nodes:
                session.add(
                    NodeExecution(
                        execution_id=execution_id,
                        node_id=node_id,
                        node_type=node_type,
                        status=NodeStatus.SKIPPED,
                        started_at=now,
                        ended_at=now,
                    )
                )

    def add_event(
        self, execution_id: str, type_: str, node_id: str | None, payload: dict[str, Any]
    ) -> int:
        with self.factory() as session, session.begin():
            seq = (
                session.scalar(
                    select(func.max(ExecutionEvent.seq)).where(
                        ExecutionEvent.execution_id == execution_id
                    )
                )
                or 0
            ) + 1
            session.add(
                ExecutionEvent(
                    execution_id=execution_id,
                    seq=seq,
                    type=type_,
                    node_id=node_id,
                    payload=payload,
                )
            )
            return seq

    def events(self, execution_id: str, after: int) -> list[ExecutionEvent]:
        query = (
            select(ExecutionEvent)
            .where(ExecutionEvent.execution_id == execution_id, ExecutionEvent.seq > after)
            .order_by(ExecutionEvent.seq)
        )
        with self.factory() as session:
            rows = list(session.scalars(query))
            session.expunge_all()
            return rows
