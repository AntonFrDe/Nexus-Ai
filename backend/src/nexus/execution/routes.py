import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nexus.api.deps import get_session
from nexus.execution.manager import ActionRefused, ExecutionManager, StartRefused
from nexus.execution.schemas import (
    ApprovalDecision,
    CheckpointRead,
    CheckpointRestore,
    EventRead,
    ExecutionDetail,
    ExecutionStart,
    ExecutionSummary,
    NodeExecutionRead,
)
from nexus.execution.states import TERMINAL, ExecutionStatus, InvalidTransition
from nexus.execution.store import ExecutionNotFound
from nexus.workflows import service
from nexus.workflows.models import WorkflowVersion
from nexus.workflows.schemas import WorkflowGraph

router = APIRouter(tags=["executions"])
HEARTBEAT_SECONDS = 15


def manager_of(request: Request) -> ExecutionManager:
    return request.app.state.execution_manager


def not_found(_request: Request, exc: ExecutionNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": f"Unknown execution: {exc}"})


def refused(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


def start_refused(_request: Request, exc: StartRefused) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc), "issues": [issue.model_dump() for issue in exc.issues]},
    )


async def _detail(manager: ExecutionManager, execution_id: str) -> ExecutionDetail:
    execution = await manager.store_call("get", execution_id)
    rows = await manager.store_call("nodes", execution_id)
    summary = ExecutionSummary.model_validate(execution).model_dump()
    return ExecutionDetail(
        **summary,
        input=execution.input,
        output=execution.output,
        nodes=[NodeExecutionRead.model_validate(row) for row in rows],
        pending_approvals=await manager.pending_approvals(execution),
    )


@router.post("/workflows/{workflow_id}/executions", response_model=ExecutionDetail, status_code=202)
async def start_execution(
    workflow_id: str,
    body: ExecutionStart = Body(default=ExecutionStart()),
    session: Session = Depends(get_session),
    manager: ExecutionManager = Depends(manager_of),
):
    document = service.to_document(service.get_workflow(session, workflow_id))
    version = session.scalar(
        select(func.max(WorkflowVersion.number)).where(WorkflowVersion.workflow_id == workflow_id)
    )
    session.commit()
    graph = WorkflowGraph.model_validate(
        document.model_dump(exclude={"id", "name", "description", "created_at", "updated_at"})
    )
    execution = await manager.start(
        graph,
        workflow_id=workflow_id,
        workflow_name=document.name,
        workflow_version=version,
        value=body.input,
        mode=body.mode,
        node_id=body.node_id,
        allow_paid=body.allow_paid,
    )
    return await _detail(manager, execution.id)


@router.get("/executions", response_model=list[ExecutionSummary])
async def list_executions(
    workflow_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    manager: ExecutionManager = Depends(manager_of),
):
    return await manager.store_call("recent", workflow_id, limit)


@router.get("/executions/{execution_id}", response_model=ExecutionDetail)
async def get_execution(execution_id: str, manager: ExecutionManager = Depends(manager_of)):
    return await _detail(manager, execution_id)


@router.get("/executions/{execution_id}/log", response_model=list[EventRead])
async def execution_log(
    execution_id: str, after: int = 0, manager: ExecutionManager = Depends(manager_of)
):
    await manager.store_call("get", execution_id)
    return await manager.store_call("events", execution_id, after)


@router.get("/executions/{execution_id}/events")
async def stream_events(
    execution_id: str,
    request: Request,
    after: int = 0,
    manager: ExecutionManager = Depends(manager_of),
):
    await manager.store_call("get", execution_id)
    resume_from = request.headers.get("last-event-id")
    start = int(resume_from) if resume_from and resume_from.isdigit() else after

    async def stream() -> AsyncIterator[str]:
        last = start
        while not await request.is_disconnected():
            events = await manager.store_call("events", execution_id, last)
            for event in events:
                last = event.seq
                body = EventRead.model_validate(event).model_dump(mode="json")
                yield f"id: {event.seq}\nevent: execution\ndata: {json.dumps(body)}\n\n"
            if not events:
                execution = await manager.store_call("get", execution_id)
                settled = (
                    ExecutionStatus(execution.status) in TERMINAL
                    or execution.status == ExecutionStatus.PAUSED
                    or execution.status == ExecutionStatus.WAITING_FOR_APPROVAL
                )
                if settled and execution_id not in manager.tasks:
                    yield "event: end\ndata: {}\n\n"
                    return
                try:
                    async with manager.changed:
                        await asyncio.wait_for(manager.changed.wait(), HEARTBEAT_SECONDS)
                except TimeoutError:
                    yield ": heartbeat\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/executions/{execution_id}/pause", status_code=202)
async def pause(execution_id: str, manager: ExecutionManager = Depends(manager_of)) -> None:
    await manager.pause(execution_id)


@router.post("/executions/{execution_id}/resume", status_code=202)
async def resume(execution_id: str, manager: ExecutionManager = Depends(manager_of)) -> None:
    await manager.resume(execution_id)


@router.post("/executions/{execution_id}/cancel", status_code=202)
async def cancel(execution_id: str, manager: ExecutionManager = Depends(manager_of)) -> None:
    await manager.cancel(execution_id)


@router.post("/executions/{execution_id}/approval", status_code=202)
async def approval(
    execution_id: str, body: ApprovalDecision, manager: ExecutionManager = Depends(manager_of)
) -> None:
    await manager.decide(execution_id, body.decision)


@router.post("/executions/{execution_id}/retry", response_model=ExecutionDetail, status_code=202)
async def retry(execution_id: str, manager: ExecutionManager = Depends(manager_of)):
    """Starts a new run with the original definition and input."""
    source = await manager.store_call("get", execution_id)
    if ExecutionStatus(source.status) not in TERMINAL:
        raise HTTPException(409, f"Cannot retry a run that is {source.status}")
    execution = await manager.start(
        WorkflowGraph.model_validate(source.graph),
        workflow_id=source.workflow_id,
        workflow_name=source.workflow_name,
        workflow_version=source.workflow_version,
        value=source.input,
        mode=source.mode,
        node_id=source.entry_node,
        allow_paid=source.allow_paid,
    )
    return await _detail(manager, execution.id)


@router.get("/executions/{execution_id}/checkpoints", response_model=list[CheckpointRead])
async def checkpoints(execution_id: str, manager: ExecutionManager = Depends(manager_of)):
    return await manager.checkpoints(execution_id)


@router.post("/executions/{execution_id}/restore", status_code=202)
async def restore(
    execution_id: str, body: CheckpointRestore, manager: ExecutionManager = Depends(manager_of)
) -> None:
    await manager.restore(execution_id, body.checkpoint_id)


EXCEPTION_HANDLERS = (
    (ExecutionNotFound, not_found),
    (ActionRefused, refused),
    (InvalidTransition, refused),
    (StartRefused, start_refused),
)
