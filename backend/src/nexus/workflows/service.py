from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nexus.workflows.migrations import migrate
from nexus.workflows.models import Workflow, WorkflowVersion
from nexus.workflows.schemas import (
    WorkflowContent,
    WorkflowCreate,
    WorkflowDocument,
    WorkflowExport,
    WorkflowGraph,
)


class WorkflowNotFound(Exception):
    pass


def _graph_of(content: WorkflowContent) -> dict[str, Any]:
    return content.model_dump(mode="json", exclude={"name", "description"})


def to_document(workflow: Workflow) -> WorkflowDocument:
    # Stored documents may predate the current schema.
    return WorkflowDocument.model_validate(
        {
            **migrate(workflow.graph),
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "created_at": workflow.created_at,
            "updated_at": workflow.updated_at,
        }
    )


def list_workflows(session: Session) -> list[Workflow]:
    return list(session.scalars(select(Workflow).order_by(Workflow.name)))


def get_workflow(session: Session, workflow_id: str) -> Workflow:
    workflow = session.get(Workflow, workflow_id)
    if workflow is None:
        raise WorkflowNotFound(workflow_id)
    return workflow


def create_workflow(session: Session, data: WorkflowCreate) -> Workflow:
    workflow = Workflow(
        name=data.name,
        description=data.description,
        graph=WorkflowGraph().model_dump(mode="json"),
    )
    session.add(workflow)
    session.flush()
    return workflow


def save_workflow(session: Session, workflow_id: str, content: WorkflowContent) -> Workflow:
    workflow = get_workflow(session, workflow_id)
    workflow.name = content.name
    workflow.description = content.description
    workflow.graph = _graph_of(content)
    session.flush()
    return workflow


def delete_workflow(session: Session, workflow_id: str) -> None:
    session.delete(get_workflow(session, workflow_id))


def duplicate_workflow(session: Session, workflow_id: str) -> Workflow:
    source = get_workflow(session, workflow_id)
    copy = Workflow(
        name=f"{source.name} copy"[:120],
        description=source.description,
        graph=source.graph,
    )
    session.add(copy)
    session.flush()
    return copy


def export_workflow(session: Session, workflow_id: str) -> WorkflowExport:
    document = to_document(get_workflow(session, workflow_id))
    return WorkflowExport(
        workflow=WorkflowContent.model_validate(
            document.model_dump(exclude={"id", "created_at", "updated_at"})
        )
    )


def parse_import(document: dict[str, Any]) -> WorkflowExport:
    """Upgrades an exported file before strict parsing, so older files stay importable."""
    workflow = document.get("workflow")
    if not isinstance(workflow, dict):
        return WorkflowExport.model_validate(document)
    return WorkflowExport.model_validate({**document, "workflow": migrate(workflow)})


def import_workflow(session: Session, document: WorkflowExport) -> Workflow:
    content = document.workflow
    workflow = Workflow(
        name=content.name, description=content.description, graph=_graph_of(content)
    )
    session.add(workflow)
    session.flush()
    return workflow


def list_versions(session: Session, workflow_id: str) -> list[WorkflowVersion]:
    get_workflow(session, workflow_id)
    query = (
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.number.desc())
    )
    return list(session.scalars(query))


def create_version(session: Session, workflow_id: str, label: str) -> WorkflowVersion:
    workflow = get_workflow(session, workflow_id)
    latest = session.scalar(
        select(func.max(WorkflowVersion.number)).where(WorkflowVersion.workflow_id == workflow_id)
    )
    version = WorkflowVersion(
        workflow_id=workflow_id,
        number=(latest or 0) + 1,
        label=label,
        name=workflow.name,
        description=workflow.description,
        graph=workflow.graph,
    )
    session.add(version)
    session.flush()
    return version


def restore_version(session: Session, workflow_id: str, number: int) -> Workflow:
    workflow = get_workflow(session, workflow_id)
    version = session.scalar(
        select(WorkflowVersion).where(
            WorkflowVersion.workflow_id == workflow_id, WorkflowVersion.number == number
        )
    )
    if version is None:
        raise WorkflowNotFound(f"{workflow_id} version {number}")
    workflow.name = version.name
    workflow.description = version.description
    workflow.graph = version.graph
    session.flush()
    return workflow
