from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from starlette.middleware.trustedhost import TrustedHostMiddleware

from nexus import __version__
from nexus.agents.routes import EXCEPTION_HANDLERS as AGENT_EXCEPTION_HANDLERS
from nexus.agents.routes import router as agents_router
from nexus.agents.service import AgentStore
from nexus.core.auth import TokenAuthMiddleware, issue_token
from nexus.core.config import Settings
from nexus.core.db import create_db_engine, run_migrations
from nexus.core.logs import LOGGER, attach_log_file
from nexus.execution.agent_nodes import AgentServices
from nexus.execution.handlers import BUILT_IN_HANDLERS
from nexus.execution.manager import ExecutionManager
from nexus.execution.routes import EXCEPTION_HANDLERS as EXECUTION_EXCEPTION_HANDLERS
from nexus.execution.routes import router as executions_router
from nexus.execution.store import ExecutionStore
from nexus.nodes.catalog import create_node_registry
from nexus.nodes.routes import router as nodes_router
from nexus.observability.langfuse import LangfuseExporter
from nexus.observability.routes import router as observability_router
from nexus.plugins.routes import EXCEPTION_HANDLERS as PLUGIN_EXCEPTION_HANDLERS
from nexus.plugins.routes import router as plugins_router
from nexus.plugins.service import PluginManager
from nexus.projects.routes import EXCEPTION_HANDLERS as PROJECT_EXCEPTION_HANDLERS
from nexus.projects.routes import router as projects_router
from nexus.projects.service import ProjectStore
from nexus.providers.adapter import LiteLLMAdapter
from nexus.providers.routes import EXCEPTION_HANDLERS as PROVIDER_EXCEPTION_HANDLERS
from nexus.providers.routes import router as providers_router
from nexus.providers.service import ProviderRegistry
from nexus.runtimes.antigravity import AntigravityRuntime
from nexus.runtimes.claude_sdk import ClaudeAgentRuntime
from nexus.runtimes.native import NativeRuntime
from nexus.runtimes.service import RuntimeRegistry
from nexus.secrets.routes import router as secrets_router
from nexus.secrets.service import SecretService, load_master_key
from nexus.settings_store.routes import router as settings_router
from nexus.workflows import service as workflow_service
from nexus.workflows.routes import not_found as workflow_not_found
from nexus.workflows.routes import router as workflows_router
from nexus.workflows.schemas import WorkflowGraph
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
        app.state.api_token = settings.api_token or issue_token(settings.data_dir)
        app.state.secrets = SecretService(app.state.session_factory, *load_master_key(settings))
        app.state.provider_registry = ProviderRegistry(
            app.state.session_factory, app.state.secrets, LiteLLMAdapter()
        )
        app.state.agents = AgentStore(app.state.session_factory)
        app.state.runtimes = RuntimeRegistry(app.state.session_factory, app.state.secrets)
        app.state.runtimes.register(NativeRuntime(app.state.provider_registry))
        app.state.runtimes.register(ClaudeAgentRuntime())
        app.state.runtimes.register(AntigravityRuntime())
        agent_services = AgentServices(
            app.state.provider_registry, app.state.runtimes, app.state.agents
        )
        handlers = {**BUILT_IN_HANDLERS, **agent_services.handlers()}
        app.state.plugins = PluginManager(
            settings,
            app.state.session_factory,
            app.state.node_registry,
            handlers,
            app.state.runtimes,
            app.state.provider_registry,
        )
        app.state.plugins.load_enabled()
        app.state.projects = ProjectStore(app.state.session_factory, app.state.agents)
        app.state.langfuse = LangfuseExporter(app.state.session_factory, app.state.secrets)
        log_handler = attach_log_file(settings.data_dir)

        def load_workflow(workflow_id: str) -> WorkflowGraph:
            with app.state.session_factory() as session:
                document = workflow_service.to_document(
                    workflow_service.get_workflow(session, workflow_id)
                )
            return WorkflowGraph.model_validate(
                document.model_dump(
                    exclude={"id", "name", "description", "created_at", "updated_at"}
                )
            )

        async with AsyncSqliteSaver.from_conn_string(str(settings.checkpoints_path)) as saver:
            manager = ExecutionManager(
                ExecutionStore(app.state.session_factory),
                app.state.node_registry,
                handlers,
                saver,
                load_workflow,
                settings.max_concurrent_executions,
                agent_services,
                app.state.langfuse,
            )
            app.state.execution_manager = manager
            await manager.recover()
            yield
            await manager.shutdown()
        LOGGER.removeHandler(log_handler)
        log_handler.close()
        engine.dispose()

    app = FastAPI(title="NEXUS", version=__version__, lifespan=lifespan)
    app.add_middleware(TokenAuthMiddleware, state=app.state)
    # Added last so it runs first: unknown hosts never reach token checks.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.state.node_registry = create_node_registry()
    app.add_exception_handler(workspace_service.WorkspaceNotFound, not_found)
    app.add_exception_handler(workflow_service.WorkflowNotFound, workflow_not_found)
    for exception, handler in (
        *EXECUTION_EXCEPTION_HANDLERS,
        *PROVIDER_EXCEPTION_HANDLERS,
        *AGENT_EXCEPTION_HANDLERS,
        *PLUGIN_EXCEPTION_HANDLERS,
        *PROJECT_EXCEPTION_HANDLERS,
    ):
        app.add_exception_handler(exception, handler)

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
    api.include_router(executions_router)
    api.include_router(secrets_router)
    api.include_router(providers_router)
    api.include_router(agents_router)
    api.include_router(plugins_router)
    api.include_router(observability_router)
    api.include_router(projects_router)
    app.include_router(api)
    return app


def run() -> None:
    import uvicorn

    settings = Settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)
