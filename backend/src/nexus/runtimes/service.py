import asyncio
from collections import defaultdict

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from nexus.core.db import Base
from nexus.providers.service import PaidCallRefused
from nexus.runtimes.base import (
    AgentRequest,
    AgentResult,
    RuntimeAdapter,
    RuntimeCapabilities,
    RuntimeError_,
    RuntimeHealth,
    UnsupportedCapability,
)
from nexus.secrets.service import SecretService


class RuntimeConfig(Base):
    __tablename__ = "runtime_configs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    secret_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class RuntimeConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    secret_name: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.\-]{1,120}$")
    enabled: bool | None = None


class RuntimeRead(BaseModel):
    id: str
    title: str
    description: str
    paid: bool
    needs_secret: bool
    enabled: bool
    secret_name: str | None
    has_secret: bool
    capabilities: RuntimeCapabilities
    health: RuntimeHealth


class RuntimeRegistry:
    def __init__(self, factory: sessionmaker[Session], secrets: SecretService) -> None:
        self.factory = factory
        self.secrets = secrets
        self.adapters: dict[str, RuntimeAdapter] = {}
        self.limits: dict[str, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(1))

    def register(self, adapter: RuntimeAdapter) -> None:
        if adapter.id in self.adapters:
            raise ValueError(f"Runtime already registered: {adapter.id}")
        self.adapters[adapter.id] = adapter
        self.limits[adapter.id] = asyncio.Semaphore(adapter.concurrency)

    def unregister(self, runtime_id: str) -> None:
        self.adapters.pop(runtime_id, None)
        self.limits.pop(runtime_id, None)

    def _config(self, runtime_id: str) -> tuple[str | None, bool]:
        with self.factory() as session:
            row = session.get(RuntimeConfig, runtime_id)
            return (row.secret_name, row.enabled) if row else (None, True)

    async def read(self, adapter: RuntimeAdapter) -> RuntimeRead:
        secret_name, enabled = self._config(adapter.id)
        return RuntimeRead(
            id=adapter.id,
            title=adapter.title,
            description=adapter.description,
            paid=adapter.paid,
            needs_secret=adapter.needs_secret,
            enabled=enabled,
            secret_name=secret_name,
            has_secret=bool(secret_name and self.secrets.exists(secret_name)),
            capabilities=adapter.capabilities,
            health=await adapter.health_check(),
        )

    async def all(self) -> list[RuntimeRead]:
        return [await self.read(adapter) for adapter in self.adapters.values()]

    def get(self, runtime_id: str) -> RuntimeAdapter | None:
        return self.adapters.get(runtime_id)

    async def configure(self, runtime_id: str, data: RuntimeConfigUpdate) -> RuntimeRead:
        adapter = self.adapters[runtime_id]
        with self.factory() as session, session.begin():
            row = session.get(RuntimeConfig, runtime_id) or RuntimeConfig(id=runtime_id)
            for name, value in data.model_dump(exclude_unset=True).items():
                setattr(row, name, value)
            session.merge(row)
        return await self.read(adapter)

    def problem(self, runtime_id: str) -> str | None:
        """Why this runtime cannot run now, checked before a workflow starts."""
        adapter = self.adapters.get(runtime_id)
        if adapter is None:
            return f"Runtime {runtime_id} is not registered"
        secret_name, enabled = self._config(runtime_id)
        if not enabled:
            return f"Runtime {adapter.title} is disabled"
        if adapter.needs_secret and not (secret_name and self.secrets.exists(secret_name)):
            return f"Runtime {adapter.title} has no API key configured"
        return None

    async def run(self, runtime_id: str, request: AgentRequest) -> AgentResult:
        adapter = self.adapters[runtime_id]
        problem = self.problem(runtime_id)
        if problem:
            raise RuntimeError_(problem)
        if adapter.paid and not request.allow_paid:
            raise PaidCallRefused(f"{adapter.title} is billed; this run does not allow paid calls")
        secret_name, _ = self._config(runtime_id)
        api_key = self.secrets.resolve(secret_name) if adapter.needs_secret else None
        async with self.limits[runtime_id]:
            try:
                return await adapter.execute(request, api_key)
            except (UnsupportedCapability, PaidCallRefused):
                raise
            except Exception as error:
                # SDK errors can quote their configuration, key included.
                text = str(error) or type(error).__name__
                raise RuntimeError_(
                    text.replace(api_key, "[redacted]") if api_key else text
                ) from None
