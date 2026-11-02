from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict

from nexus.plugins.manifest import API_VERSION
from nexus.plugins.sandbox import sandbox_available
from nexus.plugins.service import PluginManager, PluginNotFound, PluginRead, PluginRefused

router = APIRouter(prefix="/plugins", tags=["plugins"])
# The page cannot reach the API, the network or the host app: it only has the postMessage bridge.
PANEL_POLICY = (
    "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; "
    "style-src 'unsafe-inline'; img-src data:; connect-src 'none'"
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PluginInstall(Strict):
    path: str


class PluginEnable(Strict):
    granted: list[str] = []


class PluginConfig(Strict):
    config: dict[str, Any]


class PluginStatus(BaseModel):
    api_version: str
    sandbox: bool


def manager(request: Request) -> PluginManager:
    return request.app.state.plugins


@router.get("", response_model=list[PluginRead])
def list_plugins(request: Request):
    return manager(request).all()


@router.get("/status", response_model=PluginStatus)
def plugin_status():
    return PluginStatus(api_version=API_VERSION, sandbox=sandbox_available())


@router.get("/panels")
def plugin_panels(request: Request) -> list[dict[str, Any]]:
    return manager(request).enabled_panels()


@router.post("/install", response_model=PluginRead, status_code=201)
def install(body: PluginInstall, request: Request):
    return manager(request).install(body.path)


@router.post("/{plugin_id}/enable", response_model=PluginRead)
def enable(plugin_id: str, body: PluginEnable, request: Request):
    return manager(request).enable(plugin_id, body.granted)


@router.post("/{plugin_id}/disable", response_model=PluginRead)
def disable(plugin_id: str, request: Request):
    return manager(request).disable(plugin_id)


@router.put("/{plugin_id}/config", response_model=PluginRead)
def configure(plugin_id: str, body: PluginConfig, request: Request):
    return manager(request).configure(plugin_id, body.config)


@router.delete("/{plugin_id}", status_code=204)
def uninstall(plugin_id: str, request: Request) -> None:
    manager(request).uninstall(plugin_id)


@router.get("/{plugin_id}/panels/{panel_id}")
def panel_page(plugin_id: str, panel_id: str, request: Request) -> FileResponse:
    return FileResponse(
        manager(request).asset(plugin_id, panel_id),
        media_type="text/html",
        headers={"Content-Security-Policy": PANEL_POLICY, "X-Content-Type-Options": "nosniff"},
    )


def not_found(_request: Request, exc: PluginNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": f"Unknown plugin: {exc}"})


def refused(_request: Request, exc: PluginRefused) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


EXCEPTION_HANDLERS = ((PluginNotFound, not_found), (PluginRefused, refused))
