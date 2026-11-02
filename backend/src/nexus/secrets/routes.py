from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr

router = APIRouter(prefix="/secrets", tags=["secrets"])
SecretName = Annotated[str, Path(pattern=r"^[A-Za-z0-9_.\-]{1,120}$")]


class SecretWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: SecretStr = Field(min_length=1, max_length=8192)


class SecretInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    updated_at: datetime


class SecretStatus(BaseModel):
    backend: str


@router.get("", response_model=list[SecretInfo])
def list_secrets(request: Request):
    return request.app.state.secrets.names()


@router.get("/status", response_model=SecretStatus)
def secret_status(request: Request):
    return SecretStatus(backend=request.app.state.secrets.backend)


@router.put("/{name}", status_code=204)
def store_secret(name: SecretName, body: SecretWrite, request: Request) -> None:
    request.app.state.secrets.store(name, body.value.get_secret_value())


@router.delete("/{name}", status_code=204)
def delete_secret(name: SecretName, request: Request) -> None:
    if not request.app.state.secrets.delete(name):
        raise HTTPException(404, f"Unknown secret: {name}")
