from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from nexus.observability.analytics import summarize
from nexus.observability.langfuse import LangfuseConfig

router = APIRouter(tags=["observability"])


class CheckResult(BaseModel):
    ok: bool
    message: str


@router.get("/analytics")
def analytics(request: Request, days: int = Query(default=30, ge=1, le=365)) -> dict[str, Any]:
    return summarize(request.app.state.session_factory, days)


@router.get("/observability/langfuse", response_model=LangfuseConfig)
def langfuse_config(request: Request):
    return request.app.state.langfuse.config()


@router.put("/observability/langfuse", response_model=LangfuseConfig)
def save_langfuse(body: LangfuseConfig, request: Request):
    return request.app.state.langfuse.save(body)


@router.post("/observability/langfuse/check", response_model=CheckResult)
async def check_langfuse(request: Request):
    exporter = request.app.state.langfuse
    problem = await exporter.check(exporter.config())
    return CheckResult(ok=problem is None, message=problem or "Connected")
