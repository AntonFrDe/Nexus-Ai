import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from nexus.nodes.config_model import validate_config
from nexus.providers.adapter import Completion, Connection, ProviderAdapter, ProviderError
from nexus.providers.capabilities import CAPABILITIES, effective, parameter_fields
from nexus.providers.catalog import ProviderType, provider_type
from nexus.providers.models import Model, Provider
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
from nexus.secrets.service import SecretService, SecretUnavailable

TEST_MAX_TOKENS = 32


class RegistryNotFound(Exception):
    pass


class RegistryRefused(Exception):
    pass


class PaidCallRefused(Exception):
    pass


class ProviderRegistry:
    def __init__(
        self,
        factory: sessionmaker[Session],
        secrets: SecretService,
        adapter: ProviderAdapter,
    ) -> None:
        self.factory = factory
        self.secrets = secrets
        self.adapter = adapter
        # Provider types contributed by plugins.
        self.extra_types: dict[str, ProviderType] = {}
        # Local servers run one heavy model at a time.
        self.limits: dict[str, asyncio.Semaphore] = {}

    def _type(self, type_id: str) -> ProviderType:
        known = self.extra_types.get(type_id) or provider_type(type_id)
        if known is None:
            raise RegistryRefused(f"Unknown provider type: {type_id}")
        return known

    def _read(self, provider: Provider) -> ProviderRead:
        return ProviderRead(
            id=provider.id,
            type=provider.type,
            name=provider.name,
            endpoint=provider.endpoint,
            secret_name=provider.secret_name,
            has_secret=bool(provider.secret_name and self.secrets.exists(provider.secret_name)),
            enabled=provider.enabled,
            timeout_seconds=provider.timeout_seconds,
            rate_limit_rpm=provider.rate_limit_rpm,
            paid=self._type(provider.type).paid,
            created_at=provider.created_at,
        )

    def _provider(self, session: Session, provider_id: str) -> Provider:
        provider = session.get(Provider, provider_id)
        if provider is None:
            raise RegistryNotFound(f"provider {provider_id}")
        return provider

    def _model(self, session: Session, model_id: str) -> Model:
        model = session.get(Model, model_id)
        if model is None:
            raise RegistryNotFound(f"model {model_id}")
        return model

    def list_providers(self) -> list[ProviderRead]:
        with self.factory() as session:
            rows = session.scalars(select(Provider).order_by(Provider.name))
            return [self._read(row) for row in rows]

    def get_provider(self, provider_id: str) -> ProviderRead:
        with self.factory() as session:
            return self._read(self._provider(session, provider_id))

    def create_provider(self, data: ProviderCreate) -> ProviderRead:
        kind = self._type(data.type)
        endpoint = data.endpoint or kind.default_endpoint
        if kind.endpoint_required and not endpoint:
            raise RegistryRefused(f"{kind.title} needs an endpoint")
        try:
            with self.factory() as session, session.begin():
                provider = Provider(**{**data.model_dump(), "endpoint": endpoint})
                session.add(provider)
                session.flush()
                return self._read(provider)
        except IntegrityError as error:
            raise RegistryRefused(f"A provider named {data.name} already exists") from error

    def update_provider(self, provider_id: str, data: ProviderUpdate) -> ProviderRead:
        try:
            with self.factory() as session, session.begin():
                provider = self._provider(session, provider_id)
                for name, value in data.model_dump(exclude_unset=True).items():
                    setattr(provider, name, value)
                session.flush()
                return self._read(provider)
        except IntegrityError as error:
            raise RegistryRefused("That name is already used") from error

    def delete_provider(self, provider_id: str) -> None:
        with self.factory() as session, session.begin():
            session.delete(self._provider(session, provider_id))

    def _connection(self, provider: Provider) -> Connection:
        kind = self._type(provider.type)
        api_key = None
        if provider.secret_name:
            api_key = self.secrets.resolve(provider.secret_name)
        elif kind.auth == "api_key":
            raise RegistryRefused(f"{provider.name} has no API key configured")
        return Connection(kind, provider.endpoint, api_key, provider.timeout_seconds)

    def _load_connection(self, provider_id: str) -> Connection:
        with self.factory() as session:
            provider = self._provider(session, provider_id)
            if not provider.enabled:
                raise RegistryRefused(f"{provider.name} is disabled")
            return self._connection(provider)

    async def test_connection(self, provider_id: str) -> ConnectionResult:
        started = time.perf_counter()
        try:
            connection = self._load_connection(provider_id)
            if connection.provider_type.discovery == "manual":
                return ConnectionResult(
                    ok=False,
                    message="This provider has no listing to check; test a model instead",
                )
            found = await self.adapter.list_models(connection)
        except (ProviderError, RegistryRefused, SecretUnavailable) as error:
            return ConnectionResult(ok=False, message=str(error))
        return ConnectionResult(
            ok=True,
            message="Connected",
            models_found=len(found),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    def _model_read(self, session: Session, model: Model) -> ModelRead:
        provider = self._provider(session, model.provider_id)
        capabilities = effective(model.capabilities, model.capability_overrides)
        return ModelRead(
            id=model.id,
            provider_id=model.provider_id,
            provider_name=provider.name,
            model_id=model.model_id,
            context_window=model.context_window,
            capabilities=capabilities,
            capability_overrides=model.capability_overrides,
            input_cost_per_mtok=model.input_cost_per_mtok,
            output_cost_per_mtok=model.output_cost_per_mtok,
            defaults=model.defaults,
            source=model.source,
            last_test=model.last_test,
            parameter_fields=parameter_fields(capabilities),
        )

    async def discover(self, provider_id: str) -> list[ModelRead]:
        connection = self._load_connection(provider_id)
        names = await self.adapter.list_models(connection)
        facts = [await self.adapter.describe(connection, name) for name in names]
        with self.factory() as session, session.begin():
            existing = {
                row.model_id: row
                for row in session.scalars(select(Model).where(Model.provider_id == provider_id))
            }
            for fact in facts:
                row = existing.get(fact.model_id)
                if row is None:
                    row = Model(provider_id=provider_id, model_id=fact.model_id)
                    session.add(row)
                row.source = "discovered"
                row.capabilities = fact.capabilities
                row.context_window = fact.context_window or row.context_window
                if fact.input_cost_per_mtok is not None:
                    row.input_cost_per_mtok = fact.input_cost_per_mtok
                if fact.output_cost_per_mtok is not None:
                    row.output_cost_per_mtok = fact.output_cost_per_mtok
        return self.list_models(provider_id)

    def list_models(self, provider_id: str | None = None) -> list[ModelRead]:
        query = select(Model).order_by(Model.model_id)
        if provider_id:
            query = query.where(Model.provider_id == provider_id)
        with self.factory() as session:
            return [self._model_read(session, row) for row in session.scalars(query)]

    async def add_model(self, provider_id: str, data: ModelCreate) -> ModelRead:
        with self.factory() as session:
            kind = self._type(self._provider(session, provider_id).type)
        connection = Connection(kind, None, None, 60)
        facts = await self.adapter.describe(connection, data.model_id)
        try:
            with self.factory() as session, session.begin():
                model = Model(
                    provider_id=provider_id,
                    model_id=data.model_id,
                    capabilities=facts.capabilities,
                    context_window=data.context_window or facts.context_window,
                    input_cost_per_mtok=data.input_cost_per_mtok or facts.input_cost_per_mtok,
                    output_cost_per_mtok=data.output_cost_per_mtok or facts.output_cost_per_mtok,
                )
                session.add(model)
                session.flush()
                return self._model_read(session, model)
        except IntegrityError as error:
            raise RegistryRefused(f"{data.model_id} is already registered") from error

    def update_model(self, model_id: str, data: ModelUpdate) -> ModelRead:
        with self.factory() as session, session.begin():
            model = self._model(session, model_id)
            changes = data.model_dump(exclude_unset=True)
            overrides = changes.pop("capability_overrides", None)
            defaults = changes.pop("defaults", None)
            for name, value in changes.items():
                setattr(model, name, value)
            if overrides is not None:
                unknown = set(overrides) - set(CAPABILITIES)
                if unknown:
                    raise RegistryRefused(f"Unknown capabilities: {sorted(unknown)}")
                model.capability_overrides = overrides
            capabilities = effective(model.capabilities, model.capability_overrides)
            model.defaults = self._checked_defaults(
                capabilities, model.defaults if defaults is None else defaults
            )
            session.flush()
            return self._model_read(session, model)

    @staticmethod
    def _checked_defaults(
        capabilities: dict[str, bool], defaults: dict[str, Any]
    ) -> dict[str, Any]:
        problems = validate_config(
            f"parameters:{sorted(k for k, v in capabilities.items() if v)}",
            parameter_fields(capabilities),
            defaults,
        )
        if problems:
            field, message = problems[0]
            raise RegistryRefused(f"{field}: {message}")
        return defaults

    def delete_model(self, model_id: str) -> None:
        with self.factory() as session, session.begin():
            session.delete(self._model(session, model_id))

    def _resolve(self, session: Session, reference: str) -> tuple[Provider, Model] | None:
        name, separator, model_id = reference.partition("/")
        if not separator:
            return None
        provider = session.scalar(select(Provider).where(Provider.name == name))
        if provider is None:
            return None
        model = session.scalar(
            select(Model).where(Model.provider_id == provider.id, Model.model_id == model_id)
        )
        return (provider, model) if model else None

    def is_paid(self, reference: str) -> bool:
        with self.factory() as session:
            found = self._resolve(session, reference)
            return bool(found) and self._type(found[0].type).paid

    @staticmethod
    def _cost(
        answer: Completion, prices: tuple[float | None, float | None], local: bool
    ) -> float | None:
        """None means unknown, which analytics must not count as free."""
        if local:
            return 0.0
        input_price, output_price = prices
        tokens = (answer.input_tokens, answer.output_tokens)
        if None in prices or None in tokens:
            return None
        return (tokens[0] * input_price + tokens[1] * output_price) / 1_000_000

    def reference_problem(self, reference: str) -> str | None:
        with self.factory() as session:
            found = self._resolve(session, reference)
            if found is None:
                return f"Model {reference} is not in the registry"
            if not found[0].enabled:
                return f"Provider {found[0].name} is disabled"
        return None

    async def call(
        self,
        reference: str,
        prompt: str,
        system: str,
        parameters: dict[str, Any],
        allow_paid: bool,
    ) -> Completion:
        """A model call from a run. Model defaults apply, and node settings win over them."""
        with self.factory() as session:
            found = self._resolve(session, reference)
            if found is None:
                raise RegistryRefused(f"Model {reference} is not in the registry")
            provider, model = found
            kind = self._type(provider.type)
            provider_id, model_id = provider.id, model.model_id
            prices = (model.input_cost_per_mtok, model.output_cost_per_mtok)
            capabilities = effective(model.capabilities, model.capability_overrides)
            merged = self._checked_defaults(capabilities, {**model.defaults, **parameters})
        if kind.paid and not allow_paid:
            raise PaidCallRefused(f"{provider.name} is billed; this run does not allow paid calls")
        connection = self._load_connection(provider_id)
        limit = 1 if kind.local else 4
        semaphore = self.limits.setdefault(provider_id, asyncio.Semaphore(limit))
        async with semaphore:
            answer = await self.adapter.complete(connection, model_id, prompt, merged, system)
        return replace(answer, cost_usd=self._cost(answer, prices, kind.local))

    async def stream(
        self, reference: str, messages: list[dict[str, str]], allow_paid: bool
    ) -> AsyncIterator[str]:
        """A conversation reply, piece by piece, under the same paid and concurrency rules."""
        with self.factory() as session:
            found = self._resolve(session, reference)
            if found is None:
                raise RegistryRefused(f"Model {reference} is not in the registry")
            provider, model = found
            kind = self._type(provider.type)
            provider_id, model_id = provider.id, model.model_id
        if kind.paid and not allow_paid:
            raise PaidCallRefused(f"{provider.name} is billed; confirm paid calls first")
        connection = self._load_connection(provider_id)
        semaphore = self.limits.setdefault(provider_id, asyncio.Semaphore(1 if kind.local else 4))
        async with semaphore:
            async for text in self.adapter.stream(connection, model_id, messages):
                yield text

    async def test_model(self, model_id: str, request: ModelTest) -> ModelTestResult:
        """Makes one real, short call. A paid provider needs explicit confirmation first."""
        with self.factory() as session:
            model = self._model(session, model_id)
            provider = self._provider(session, model.provider_id)
            name = model.model_id
            defaults = dict(model.defaults)
            provider_id = provider.id
            paid = self._type(provider.type).paid
        if paid and not request.confirm_paid:
            raise RegistryRefused("This call may cost money and needs confirmation")
        now = datetime.now(UTC)
        try:
            connection = self._load_connection(provider_id)
            parameters = {**defaults, "max_tokens": TEST_MAX_TOKENS}
            answer = await self.adapter.complete(connection, name, request.prompt, parameters)
            result = ModelTestResult(
                ok=True,
                message="The model answered",
                text=answer.text,
                served_by=answer.model,
                input_tokens=answer.input_tokens,
                output_tokens=answer.output_tokens,
                latency_ms=answer.latency_ms,
                tested_at=now,
            )
        except (ProviderError, RegistryRefused, SecretUnavailable) as error:
            result = ModelTestResult(ok=False, message=str(error), tested_at=now)
        with self.factory() as session, session.begin():
            self._model(session, model_id).last_test = {
                "ok": result.ok,
                "message": result.message,
                "latency_ms": result.latency_ms,
                "tested_at": now.isoformat(),
            }
        return result
