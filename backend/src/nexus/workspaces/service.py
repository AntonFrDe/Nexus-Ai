from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nexus.workspaces.models import Workspace
from nexus.workspaces.presets import DEFAULT_WORKSPACES
from nexus.workspaces.schemas import (
    WorkspaceCreate,
    WorkspaceExport,
    WorkspaceExportBody,
    WorkspaceUpdate,
)


class WorkspaceNotFound(Exception):
    pass


def _next_position(session: Session) -> int:
    return (session.scalar(select(func.max(Workspace.position))) or 0) + 1


def seed_defaults(session: Session) -> None:
    if session.scalar(select(func.count()).select_from(Workspace)):
        return
    for position, (name, preset, description) in enumerate(DEFAULT_WORKSPACES):
        session.add(
            Workspace(name=name, preset=preset, description=description, position=position)
        )


def list_workspaces(session: Session) -> list[Workspace]:
    return list(session.scalars(select(Workspace).order_by(Workspace.position, Workspace.name)))


def get_workspace(session: Session, workspace_id: str) -> Workspace:
    workspace = session.get(Workspace, workspace_id)
    if workspace is None:
        raise WorkspaceNotFound(workspace_id)
    return workspace


def create_workspace(session: Session, data: WorkspaceCreate) -> Workspace:
    workspace = Workspace(**data.model_dump(), position=_next_position(session))
    session.add(workspace)
    session.flush()
    return workspace


def update_workspace(session: Session, workspace_id: str, data: WorkspaceUpdate) -> Workspace:
    workspace = get_workspace(session, workspace_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(workspace, field, value)
    session.flush()
    return workspace


def delete_workspace(session: Session, workspace_id: str) -> None:
    session.delete(get_workspace(session, workspace_id))


def duplicate_workspace(session: Session, workspace_id: str, name: str | None) -> Workspace:
    source = get_workspace(session, workspace_id)
    copy = Workspace(
        name=name or f"{source.name} copy",
        description=source.description,
        preset=source.preset,
        layout=source.layout,
        panel_states=source.panel_states,
        preferences=source.preferences,
        position=_next_position(session),
    )
    session.add(copy)
    session.flush()
    return copy


def export_workspace(session: Session, workspace_id: str) -> WorkspaceExport:
    workspace = get_workspace(session, workspace_id)
    return WorkspaceExport(
        workspace=WorkspaceExportBody(
            name=workspace.name,
            description=workspace.description,
            preset=workspace.preset,
            layout=workspace.layout,
            panel_states=workspace.panel_states,
            preferences=workspace.preferences,
        )
    )


def import_workspace(session: Session, document: WorkspaceExport) -> Workspace:
    workspace = Workspace(**document.workspace.model_dump(), position=_next_position(session))
    session.add(workspace)
    session.flush()
    return workspace
