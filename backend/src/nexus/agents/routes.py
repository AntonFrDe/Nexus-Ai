from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from nexus.agents.definition import AGENT_FIELDS
from nexus.agents.service import AgentNotFound, AgentRefused, AgentStore
from nexus.agents.templates import AGENT_TEMPLATES, AgentTemplate
from nexus.nodes.spec import FieldSpec
from nexus.runtimes.base import UnsupportedCapability
from nexus.runtimes.service import RuntimeConfigUpdate, RuntimeRead

router = APIRouter(tags=["agents"])
Name = Annotated[str, Field(min_length=1, max_length=120)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentCreate(Strict):
    name: Name
    template: str | None = None


class AgentUpdate(Strict):
    name: Name | None = None
    definition: dict[str, Any] | None = None


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    version: int
    template: str | None
    definition: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AgentVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    number: int
    name: str
    definition: dict[str, Any]
    created_at: datetime


def store(request: Request) -> AgentStore:
    return request.app.state.agents


@router.get("/agent-fields", response_model=list[FieldSpec])
def agent_fields():
    return AGENT_FIELDS


@router.get("/agent-templates", response_model=list[AgentTemplate])
def agent_templates():
    return AGENT_TEMPLATES


@router.get("/agents", response_model=list[AgentRead])
def list_agents(request: Request):
    return store(request).all()


@router.post("/agents", response_model=AgentRead, status_code=201)
def create_agent(body: AgentCreate, request: Request):
    return store(request).create(body.name, body.template)


@router.get("/agents/{agent_id}", response_model=AgentRead)
def get_agent(agent_id: str, request: Request):
    return store(request).get(agent_id)


@router.patch("/agents/{agent_id}", response_model=AgentRead)
def update_agent(agent_id: str, body: AgentUpdate, request: Request):
    return store(request).update(agent_id, body.name, body.definition)


@router.delete("/agents/{agent_id}", status_code=204)
def delete_agent(agent_id: str, request: Request) -> None:
    store(request).delete(agent_id)


@router.post("/agents/{agent_id}/clone", response_model=AgentRead, status_code=201)
def clone_agent(agent_id: str, request: Request):
    return store(request).clone(agent_id)


@router.get("/agents/{agent_id}/versions", response_model=list[AgentVersionRead])
def agent_versions(agent_id: str, request: Request):
    return store(request).versions(agent_id)


@router.post("/agents/{agent_id}/versions/{number}/restore", response_model=AgentRead)
def restore_agent(agent_id: str, number: int, request: Request):
    return store(request).restore(agent_id, number)


@router.get("/runtimes", response_model=list[RuntimeRead])
async def list_runtimes(request: Request):
    return await request.app.state.runtimes.all()


@router.patch("/runtimes/{runtime_id}", response_model=RuntimeRead)
async def configure_runtime(runtime_id: str, body: RuntimeConfigUpdate, request: Request):
    registry = request.app.state.runtimes
    if registry.get(runtime_id) is None:
        raise HTTPException(404, f"Unknown runtime: {runtime_id}")
    return await registry.configure(runtime_id, body)


def not_found(_request: Request, exc: AgentNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": f"Unknown agent: {exc}"})


def refused(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


def unsupported(_request: Request, exc: UnsupportedCapability) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"detail": str(exc), "runtime": exc.runtime, "capability": exc.capability},
    )


EXCEPTION_HANDLERS = (
    (AgentNotFound, not_found),
    (AgentRefused, refused),
    (UnsupportedCapability, unsupported),
)
