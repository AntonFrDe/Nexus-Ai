from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from nexus.api.deps import get_session
from nexus.workflows import service
from nexus.workflows.migrations import UnsupportedSchemaVersion
from nexus.workflows.schemas import (
    ValidationReport,
    VersionCreate,
    VersionSummary,
    WorkflowContent,
    WorkflowCreate,
    WorkflowDocument,
    WorkflowExport,
    WorkflowGraph,
    WorkflowSummary,
)
from nexus.workflows.validation import validate_workflow

router = APIRouter(prefix="/workflows", tags=["workflows"])


def not_found(_request: Request, exc: service.WorkflowNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": f"Unknown workflow: {exc}"})


@router.get("", response_model=list[WorkflowSummary])
def list_workflows(session: Session = Depends(get_session)):
    return service.list_workflows(session)


@router.post("", response_model=WorkflowDocument, status_code=201)
def create_workflow(body: WorkflowCreate, session: Session = Depends(get_session)):
    return service.to_document(service.create_workflow(session, body))


@router.post("/validate", response_model=ValidationReport)
def validate(body: WorkflowGraph, request: Request):
    return validate_workflow(body, request.app.state.node_registry)


@router.post("/import", response_model=WorkflowDocument, status_code=201)
def import_workflow(body: dict[str, Any] = Body(...), session: Session = Depends(get_session)):
    try:
        document = service.parse_import(body)
    except UnsupportedSchemaVersion as error:
        raise HTTPException(422, str(error)) from error
    except ValidationError as error:
        raise HTTPException(422, error.errors(include_url=False, include_input=False)) from error
    return service.to_document(service.import_workflow(session, document))


@router.get("/{workflow_id}", response_model=WorkflowDocument)
def get_workflow(workflow_id: str, session: Session = Depends(get_session)):
    return service.to_document(service.get_workflow(session, workflow_id))


@router.put("/{workflow_id}", response_model=WorkflowDocument)
def save_workflow(workflow_id: str, body: WorkflowContent, session: Session = Depends(get_session)):
    return service.to_document(service.save_workflow(session, workflow_id, body))


@router.delete("/{workflow_id}", status_code=204)
def delete_workflow(workflow_id: str, session: Session = Depends(get_session)) -> None:
    service.delete_workflow(session, workflow_id)


@router.post("/{workflow_id}/duplicate", response_model=WorkflowDocument, status_code=201)
def duplicate_workflow(workflow_id: str, session: Session = Depends(get_session)):
    return service.to_document(service.duplicate_workflow(session, workflow_id))


@router.get("/{workflow_id}/export", response_model=WorkflowExport)
def export_workflow(workflow_id: str, session: Session = Depends(get_session)):
    return service.export_workflow(session, workflow_id)


@router.get("/{workflow_id}/versions", response_model=list[VersionSummary])
def list_versions(workflow_id: str, session: Session = Depends(get_session)):
    return service.list_versions(session, workflow_id)


@router.post("/{workflow_id}/versions", response_model=VersionSummary, status_code=201)
def create_version(workflow_id: str, body: VersionCreate, session: Session = Depends(get_session)):
    return service.create_version(session, workflow_id, body.label)


@router.post("/{workflow_id}/versions/{number}/restore", response_model=WorkflowDocument)
def restore_version(workflow_id: str, number: int, session: Session = Depends(get_session)):
    return service.to_document(service.restore_version(session, workflow_id, number))
