from alembic import context
from sqlalchemy import create_engine

from nexus.agents import models as _agent_models  # noqa: F401
from nexus.core.config import Settings
from nexus.core.db import Base, sqlite_url
from nexus.execution import models as _execution_models  # noqa: F401
from nexus.providers import models as _provider_models  # noqa: F401
from nexus.runtimes import service as _runtime_models  # noqa: F401
from nexus.secrets import models as _secret_models  # noqa: F401
from nexus.settings_store import models as _settings_models  # noqa: F401
from nexus.workflows import models as _workflow_models  # noqa: F401
from nexus.workspaces import models as _workspace_models  # noqa: F401

url = context.config.get_main_option("sqlalchemy.url") or sqlite_url(Settings())
engine = create_engine(url)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
