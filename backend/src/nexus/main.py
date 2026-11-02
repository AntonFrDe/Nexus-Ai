from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from starlette.middleware.trustedhost import TrustedHostMiddleware

from nexus import __version__
from nexus.core.config import Settings
from nexus.core.db import create_db_engine, run_migrations
from nexus.nodes.catalog import create_node_registry
from nexus.nodes.routes import router as nodes_router
from nexus.settings_store.routes import router as settings_router
from nexus.workflows import service as workflow_service
from nexus.workflows.routes import not_found as workflow_not_found
from nexus.workflows.routes import router as workflows_router
from nexus.workspaces import service as workspace_service
from nexus.workspaces.routes import not_found
from nexus.workspaces.routes import router as workspaces_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        run_migrations(settings)
        engine = create_db_engine(settings)
        app.state.session_factory = sessionmaker(engine, expire_on_commit=False)
        with app.state.session_factory() as session, session.begin():
            workspace_service.seed_defaults(session)
        yield
        engine.dispose()

    app = FastAPI(title="NEXUS", version=__version__, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.state.node_registry = create_node_registry()
    app.add_exception_handler(workspace_service.WorkspaceNotFound, not_found)
    app.add_exception_handler(workflow_service.WorkflowNotFound, workflow_not_found)

    api = APIRouter(prefix="/api")

    @api.get("/health", tags=["system"])
    def health(request: Request) -> dict[str, str]:
        with request.app.state.session_factory() as session:
            session.execute(text("SELECT 1"))
        return {"status": "ok", "version": __version__, "database": "sqlite"}

    api.include_router(workspaces_router)
    api.include_router(settings_router)
    api.include_router(nodes_router)
    api.include_router(workflows_router)
    app.include_router(api)
    return app


def run() -> None:
    import uvicorn

    settings = Settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)
