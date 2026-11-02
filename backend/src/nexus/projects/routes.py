import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from nexus.projects.proposals import SYSTEM_PROMPT, split_proposal
from nexus.projects.service import ProjectNotFound, ProjectRefused, ProjectStore

router = APIRouter(prefix="/projects", tags=["projects"])
Name = Annotated[str, Field(min_length=1, max_length=120)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectCreate(Strict):
    name: Name
    description: str = Field(default="", max_length=2000)


class ProjectUpdate(Strict):
    name: Name | None = None
    description: str | None = Field(default=None, max_length=2000)


class ChatRequest(Strict):
    content: str = Field(min_length=1, max_length=20000)
    model: str = Field(min_length=1, max_length=320)
    allow_paid: bool = False


class ProjectSummary(BaseModel):
    id: str
    name: str
    description: str
    updated_at: datetime
    messages: int
    results: int


class MessageRead(BaseModel):
    id: str
    role: str
    content: str
    model: str | None
    proposal: dict[str, Any] | None
    proposal_status: str | None
    created_at: datetime


class ResultRead(BaseModel):
    id: str
    kind: str
    title: str
    content: dict[str, Any]
    created_at: datetime


class ProjectDetail(BaseModel):
    id: str
    name: str
    description: str
    updated_at: datetime
    messages: list[MessageRead]
    results: list[ResultRead]


def store(request: Request) -> ProjectStore:
    return request.app.state.projects


@router.get("", response_model=list[ProjectSummary])
def list_projects(request: Request):
    return store(request).all()


@router.post("", response_model=ProjectDetail, status_code=201)
def create_project(body: ProjectCreate, request: Request):
    project = store(request).create(body.name, body.description)
    return store(request).detail(project.id)


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str, request: Request):
    return store(request).detail(project_id)


@router.patch("/{project_id}", response_model=ProjectDetail)
def update_project(project_id: str, body: ProjectUpdate, request: Request):
    store(request).update(project_id, body.name, body.description)
    return store(request).detail(project_id)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, request: Request) -> None:
    store(request).delete(project_id)


@router.post("/{project_id}/messages/{message_id}/approve", response_model=ProjectDetail)
def approve(project_id: str, message_id: str, request: Request):
    store(request).approve(project_id, message_id)
    return store(request).detail(project_id)


@router.post("/{project_id}/messages/{message_id}/reject", response_model=ProjectDetail)
def reject(project_id: str, message_id: str, request: Request):
    store(request).reject(project_id, message_id)
    return store(request).detail(project_id)


def _event(name: str, data: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


@router.post("/{project_id}/chat")
async def chat(project_id: str, body: ChatRequest, request: Request) -> StreamingResponse:
    projects = store(request)
    registry = request.app.state.provider_registry
    problem = registry.reference_problem(body.model)
    if problem:
        raise ProjectRefused(problem)
    projects.add_message(project_id, "user", body.content)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *projects.history(project_id)]

    async def stream() -> AsyncIterator[str]:
        parts: list[str] = []
        try:
            async for delta in registry.stream(body.model, messages, body.allow_paid):
                parts.append(delta)
                yield _event("delta", {"text": delta})
        except Exception as error:
            yield _event("failure", {"message": str(error)})
            return
        finally:
            # Keep what was written even when the page closes during the reply.
            text, proposal = split_proposal("".join(parts))
            saved = (
                projects.add_message(project_id, "assistant", text, body.model, proposal)
                if text or proposal
                else None
            )
        yield _event("done", {"message_id": saved["id"] if saved else None})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def not_found(_request: Request, exc: ProjectNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": f"Unknown project: {exc}"})


def refused(_request: Request, exc: ProjectRefused) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


EXCEPTION_HANDLERS = ((ProjectNotFound, not_found), (ProjectRefused, refused))
