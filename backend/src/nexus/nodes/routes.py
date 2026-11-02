from typing import Any

from fastapi import APIRouter, Request

from nexus.nodes.catalog import RUNTIME_FIELDS
from nexus.nodes.registry import PORT_COMPATIBILITY
from nexus.workflows.migrations import CURRENT_SCHEMA_VERSION

router = APIRouter(prefix="/node-types", tags=["nodes"])


@router.get("")
def node_catalog(request: Request) -> dict[str, Any]:
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "node_types": [node.model_dump() for node in request.app.state.node_registry.list()],
        "runtime_fields": [field.model_dump() for field in RUNTIME_FIELDS],
        "port_compatibility": PORT_COMPATIBILITY,
    }
