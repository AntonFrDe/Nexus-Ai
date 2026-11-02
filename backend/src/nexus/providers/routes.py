from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from nexus.providers.adapter import ProviderError
from nexus.providers.capabilities import CAPABILITIES
from nexus.providers.catalog import PROVIDER_TYPES, ProviderType
from nexus.providers.schemas import (
    ConnectionResult,
    ModelCreate,
    ModelRead,
    ModelTest,
    ModelTestResult,
    ModelUpdate,
    ProviderCreate,
    ProviderRead,
    ProviderUpdate,
)
from nexus.providers.service import ProviderRegistry, RegistryNotFound, RegistryRefused
from nexus.secrets.service import SecretUnavailable

router = APIRouter(tags=["models"])


def registry(request: Request) -> ProviderRegistry:
    return request.app.state.provider_registry


def not_found(_request: Request, exc: RegistryNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": f"Unknown {exc}"})


def refused(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


def unreachable(_request: Request, exc: ProviderError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@router.get("/provider-types", response_model=list[ProviderType])
def provider_types(request: Request):
    return [*PROVIDER_TYPES, *registry(request).extra_types.values()]


@router.get("/capabilities", response_model=list[str])
def capabilities():
    return CAPABILITIES


@router.get("/providers", response_model=list[ProviderRead])
def list_providers(request: Request):
    return registry(request).list_providers()


@router.post("/providers", response_model=ProviderRead, status_code=201)
def create_provider(body: ProviderCreate, request: Request):
    return registry(request).create_provider(body)


@router.get("/providers/{provider_id}", response_model=ProviderRead)
def get_provider(provider_id: str, request: Request):
    return registry(request).get_provider(provider_id)


@router.patch("/providers/{provider_id}", response_model=ProviderRead)
def update_provider(provider_id: str, body: ProviderUpdate, request: Request):
    return registry(request).update_provider(provider_id, body)


@router.delete("/providers/{provider_id}", status_code=204)
def delete_provider(provider_id: str, request: Request) -> None:
    registry(request).delete_provider(provider_id)


@router.post("/providers/{provider_id}/test", response_model=ConnectionResult)
async def test_connection(provider_id: str, request: Request):
    return await registry(request).test_connection(provider_id)


@router.post("/providers/{provider_id}/discover", response_model=list[ModelRead])
async def discover(provider_id: str, request: Request):
    return await registry(request).discover(provider_id)


@router.post("/providers/{provider_id}/models", response_model=ModelRead, status_code=201)
async def add_model(provider_id: str, body: ModelCreate, request: Request):
    return await registry(request).add_model(provider_id, body)


@router.get("/models", response_model=list[ModelRead])
def list_models(request: Request, provider_id: str | None = None):
    return registry(request).list_models(provider_id)


@router.patch("/models/{model_id}", response_model=ModelRead)
def update_model(model_id: str, body: ModelUpdate, request: Request):
    return registry(request).update_model(model_id, body)


@router.delete("/models/{model_id}", status_code=204)
def delete_model(model_id: str, request: Request) -> None:
    registry(request).delete_model(model_id)


@router.post("/models/{model_id}/test", response_model=ModelTestResult)
async def test_model(model_id: str, body: ModelTest, request: Request):
    return await registry(request).test_model(model_id, body)


EXCEPTION_HANDLERS = (
    (RegistryNotFound, not_found),
    (RegistryRefused, refused),
    (SecretUnavailable, refused),
    (ProviderError, unreachable),
)
