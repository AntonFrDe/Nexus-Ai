from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nexus.api.deps import get_session
from nexus.workspaces import service
from nexus.workspaces.schemas import (
    WorkspaceCreate,
    WorkspaceDetail,
    WorkspaceExport,
    WorkspaceSummary,
    WorkspaceUpdate,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class DuplicateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)


def not_found(_request: Request, exc: service.WorkspaceNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": f"Unknown workspace: {exc}"})


@router.get("", response_model=list[WorkspaceSummary])
def list_workspaces(session: Session = Depends(get_session)):
    return service.list_workspaces(session)


@router.post("", response_model=WorkspaceDetail, status_code=201)
def create_workspace(body: WorkspaceCreate, session: Session = Depends(get_session)):
    return service.create_workspace(session, body)


@router.post("/import", response_model=WorkspaceDetail, status_code=201)
def import_workspace(body: WorkspaceExport, session: Session = Depends(get_session)):
    return service.import_workspace(session, body)


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
def get_workspace(workspace_id: str, session: Session = Depends(get_session)):
    return service.get_workspace(session, workspace_id)


@router.patch("/{workspace_id}", response_model=WorkspaceDetail)
def update_workspace(
    workspace_id: str, body: WorkspaceUpdate, session: Session = Depends(get_session)
):
    if "name" in body.model_fields_set and body.name is None:
        raise HTTPException(422, "name cannot be null")
    return service.update_workspace(session, workspace_id, body)


@router.delete("/{workspace_id}", status_code=204)
def delete_workspace(workspace_id: str, session: Session = Depends(get_session)) -> None:
    if len(service.list_workspaces(session)) == 1:
        raise HTTPException(409, "The last workspace cannot be deleted")
    service.delete_workspace(session, workspace_id)


@router.post("/{workspace_id}/duplicate", response_model=WorkspaceDetail, status_code=201)
def duplicate_workspace(
    workspace_id: str, body: DuplicateRequest, session: Session = Depends(get_session)
):
    return service.duplicate_workspace(session, workspace_id, body.name)


@router.get("/{workspace_id}/export", response_model=WorkspaceExport)
def export_workspace(workspace_id: str, session: Session = Depends(get_session)):
    return service.export_workspace(session, workspace_id)
