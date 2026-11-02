import shutil
import tempfile
from pathlib import Path
from typing import Any

from packaging.specifiers import SpecifierSet
from packaging.version import Version
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from nexus.core.config import Settings
from nexus.execution.context import NodeContext, NodeHandler, NodeResult
from nexus.nodes.config_model import validate_config
from nexus.nodes.registry import NodeRegistry
from nexus.plugins.manifest import API_VERSION, MANIFEST_FILE, PluginManifest
from nexus.plugins.models import InstalledPlugin
from nexus.plugins.sandbox import call_plugin, sandbox_available
from nexus.providers.catalog import ProviderType
from nexus.providers.service import ProviderRegistry
from nexus.runtimes.base import AgentRequest, AgentResult, RuntimeAdapter, RuntimeCapabilities
from nexus.runtimes.service import RuntimeRegistry

MAX_PLUGIN_BYTES = 50_000_000


class PluginRefused(Exception):
    pass


class PluginNotFound(Exception):
    pass


class PluginRead(BaseModel):
    id: str
    name: str
    version: str
    description: str
    author: str
    category: str
    nexus_api: str
    compatible: bool
    enabled: bool
    permissions: list[str]
    granted: list[str]
    dependencies: dict[str, str]
    contributions: dict[str, list[str]]
    config_fields: list[Any]
    config: dict[str, Any]
    problem: str | None = None


class PluginRuntime(RuntimeAdapter):
    """An agent runtime written by a plugin, called through the same sandbox as its nodes."""

    paid = False
    needs_secret = False
    capabilities = RuntimeCapabilities(interruptible=True)

    def __init__(self, manager: "PluginManager", plugin_id: str, contribution) -> None:
        self.manager = manager
        self.plugin_id = plugin_id
        self.id = contribution.id
        self.title = contribution.title
        self.description = contribution.description or "Provided by a plugin"

    async def execute(self, request: AgentRequest, api_key: str | None) -> AgentResult:
        payload = {
            "prompt": request.prompt,
            "model": request.model,
            "system_prompt": request.system_prompt,
        }
        result = await self.manager.call(self.plugin_id, "runtime", self.id, payload)
        if not isinstance(result, dict) or not isinstance(result.get("text"), str):
            raise ValueError("The runtime must return a text field")
        return AgentResult(text=result["text"], runtime=self.id, model=request.model)


class PluginManager:
    def __init__(
        self,
        settings: Settings,
        factory: sessionmaker[Session],
        nodes: NodeRegistry,
        handlers: dict[str, NodeHandler],
        runtimes: RuntimeRegistry,
        providers: ProviderRegistry,
    ) -> None:
        self.settings = settings
        self.factory = factory
        self.nodes = nodes
        self.handlers = handlers
        self.runtimes = runtimes
        self.providers = providers
        self.directory = settings.data_dir / "plugins"
        self.data_directory = settings.data_dir / "plugin-data"
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.data_directory.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Files

    def _manifest(self, plugin_dir: Path) -> PluginManifest:
        path = plugin_dir / MANIFEST_FILE
        if not path.is_file():
            raise PluginRefused(f"No {MANIFEST_FILE} in {plugin_dir}")
        try:
            return PluginManifest.model_validate_json(path.read_bytes())
        except ValidationError as error:
            first = error.errors(include_url=False, include_input=False)[0]
            where = ".".join(str(part) for part in first["loc"])
            raise PluginRefused(f"Invalid manifest: {where} {first['msg']}".strip()) from error

    @staticmethod
    def _check_package(source: Path, manifest: PluginManifest) -> None:
        total = 0
        for path in source.rglob("*"):
            if path.is_symlink():
                raise PluginRefused(f"Plugins cannot contain symbolic links: {path.name}")
            if path.is_file():
                total += path.stat().st_size
        if total > MAX_PLUGIN_BYTES:
            raise PluginRefused("The plugin is larger than 50 MB")
        needed = [panel.page for panel in manifest.contributions.panels]
        if manifest.entry_points.backend:
            needed.append(manifest.entry_points.backend)
        for name in needed:
            if not (source / name).is_file():
                raise PluginRefused(f"The plugin is missing {name}")

    def install(self, source_path: str) -> PluginRead:
        """Copies files and reads the manifest. Nothing from the plugin runs until it is enabled."""
        source = Path(source_path).expanduser()
        if not source.is_dir():
            raise PluginRefused(f"{source_path} is not a folder")
        manifest = self._manifest(source)
        self._check_package(source, manifest)
        with self.factory() as session, session.begin():
            row = session.get(InstalledPlugin, manifest.id)
            if row is not None:
                if Version(manifest.version) <= Version(row.version):
                    raise PluginRefused(f"Version {row.version} is already installed")
                if row.enabled:
                    self._unload(self._manifest(self.directory / manifest.id))
                if not set(manifest.permissions) <= set(row.granted):
                    row.enabled = False
                    row.granted = []
                row.version = manifest.version
            else:
                session.add(InstalledPlugin(id=manifest.id, version=manifest.version))
            target = self.directory / manifest.id
            with tempfile.TemporaryDirectory(dir=self.directory) as work:
                staged = Path(work) / "package"
                shutil.copytree(source, staged)
                shutil.rmtree(target, ignore_errors=True)
                staged.rename(target)
            session.flush()
            enabled = session.get(InstalledPlugin, manifest.id).enabled
        if enabled:
            self._load(manifest)
        return self.get(manifest.id)

    def uninstall(self, plugin_id: str) -> None:
        with self.factory() as session:
            rows = list(session.scalars(select(InstalledPlugin)))
        self._require(rows, plugin_id)
        for row in rows:
            if row.id != plugin_id and plugin_id in self._read_manifest(row).dependencies:
                raise PluginRefused(f"{row.id} depends on this plugin")
        manifest = self._read_manifest(self._require(rows, plugin_id))
        self._check_not_in_use(manifest)
        if self._require(rows, plugin_id).enabled:
            self._unload(manifest)
        with self.factory() as session, session.begin():
            session.delete(session.get(InstalledPlugin, plugin_id))
        shutil.rmtree(self.directory / plugin_id, ignore_errors=True)
        shutil.rmtree(self.data_directory / plugin_id, ignore_errors=True)

    @staticmethod
    def _require(rows: list[InstalledPlugin], plugin_id: str) -> InstalledPlugin:
        for row in rows:
            if row.id == plugin_id:
                return row
        raise PluginNotFound(plugin_id)

    def _read_manifest(self, row: InstalledPlugin) -> PluginManifest:
        return self._manifest(self.directory / row.id)

    # State

    def _row(self, plugin_id: str) -> InstalledPlugin:
        with self.factory() as session:
            row = session.get(InstalledPlugin, plugin_id)
            if row is None:
                raise PluginNotFound(plugin_id)
            session.expunge(row)
            return row

    def _describe(self, row: InstalledPlugin) -> PluginRead:
        try:
            manifest = self._read_manifest(row)
        except PluginRefused as error:
            return PluginRead(
                id=row.id,
                name=row.id,
                version=row.version,
                description="",
                author="",
                category="integration",
                nexus_api="",
                compatible=False,
                enabled=False,
                permissions=[],
                granted=row.granted,
                dependencies={},
                contributions={},
                config_fields=[],
                config=row.config,
                problem=str(error),
            )
        contributions = manifest.contributions
        return PluginRead(
            id=manifest.id,
            name=manifest.name,
            version=manifest.version,
            description=manifest.description,
            author=manifest.author,
            category=manifest.category,
            nexus_api=manifest.nexus_api,
            compatible=API_VERSION in SpecifierSet(manifest.nexus_api),
            enabled=row.enabled,
            permissions=manifest.permissions,
            granted=row.granted,
            dependencies=manifest.dependencies,
            contributions={
                "nodes": [item.title for item in contributions.nodes],
                "panels": [item.title for item in contributions.panels],
                "runtimes": [item.title for item in contributions.runtimes],
                "providers": [item.title for item in contributions.providers],
            },
            config_fields=[field.model_dump() for field in manifest.config],
            config=row.config,
        )

    def all(self) -> list[PluginRead]:
        with self.factory() as session:
            rows = list(session.scalars(select(InstalledPlugin).order_by(InstalledPlugin.id)))
            session.expunge_all()
        return [self._describe(row) for row in rows]

    def get(self, plugin_id: str) -> PluginRead:
        return self._describe(self._row(plugin_id))

    def enabled_panels(self) -> list[dict[str, Any]]:
        panels = []
        for plugin in self.all():
            if plugin.enabled:
                manifest = self._manifest(self.directory / plugin.id)
                panels += [
                    {**panel.model_dump(), "plugin_id": plugin.id}
                    for panel in manifest.contributions.panels
                ]
        return panels

    def asset(self, plugin_id: str, panel_id: str) -> Path:
        """Only pages declared by an enabled plugin are served, so no path comes from the URL."""
        row = self._row(plugin_id)
        if not row.enabled:
            raise PluginNotFound(plugin_id)
        manifest = self._read_manifest(row)
        for panel in manifest.contributions.panels:
            if panel.id == panel_id:
                return (self.directory / plugin_id / panel.page).resolve()
        raise PluginNotFound(f"{plugin_id} panel {panel_id}")

    # Lifecycle

    def enable(self, plugin_id: str, granted: list[str]) -> PluginRead:
        row = self._row(plugin_id)
        manifest = self._read_manifest(row)
        if API_VERSION not in SpecifierSet(manifest.nexus_api):
            raise PluginRefused(f"This plugin needs NEXUS API {manifest.nexus_api}")
        if set(manifest.permissions) != set(granted):
            raise PluginRefused("Every requested permission must be accepted")
        if manifest.entry_points.backend and not sandbox_available():
            raise PluginRefused("Code plugins need the macOS sandbox, which is not available here")
        self._check_dependencies(manifest)
        if row.enabled:
            return self.get(plugin_id)
        self._check_conflicts(manifest)
        with self.factory() as session, session.begin():
            stored = session.get(InstalledPlugin, plugin_id)
            stored.enabled = True
            stored.granted = list(granted)
        self._load(manifest)
        return self.get(plugin_id)

    def disable(self, plugin_id: str) -> PluginRead:
        row = self._row(plugin_id)
        manifest = self._read_manifest(row)
        for other in self.all():
            if other.enabled and plugin_id in other.dependencies:
                raise PluginRefused(f"{other.id} depends on this plugin")
        self._check_not_in_use(manifest)
        if row.enabled:
            self._unload(manifest)
        with self.factory() as session, session.begin():
            session.get(InstalledPlugin, plugin_id).enabled = False
        return self.get(plugin_id)

    def configure(self, plugin_id: str, config: dict[str, Any]) -> PluginRead:
        manifest = self._read_manifest(self._row(plugin_id))
        problems = validate_config(f"plugin:{plugin_id}", manifest.config, config)
        if problems:
            raise PluginRefused(f"{problems[0][0]}: {problems[0][1]}")
        with self.factory() as session, session.begin():
            session.get(InstalledPlugin, plugin_id).config = config
        return self.get(plugin_id)

    def _check_dependencies(self, manifest: PluginManifest) -> None:
        installed = {plugin.id: plugin for plugin in self.all()}
        for name, spec in manifest.dependencies.items():
            dependency = installed.get(name)
            if dependency is None or not dependency.enabled:
                raise PluginRefused(f"Needs plugin {name}, enabled")
            if dependency.version not in SpecifierSet(spec):
                raise PluginRefused(f"Needs {name} {spec}, found {dependency.version}")

    def _check_conflicts(self, manifest: PluginManifest) -> None:
        for node in manifest.contributions.nodes:
            if self.nodes.get(node.type):
                raise PluginRefused(f"Node type {node.type} already exists")
        for runtime in manifest.contributions.runtimes:
            if self.runtimes.get(runtime.id):
                raise PluginRefused(f"Runtime {runtime.id} already exists")
        for provider in manifest.contributions.providers:
            if provider.id in self.providers.extra_types:
                raise PluginRefused(f"Provider type {provider.id} already exists")

    def _check_not_in_use(self, manifest: PluginManifest) -> None:
        for provider in self.providers.list_providers():
            if provider.type in {item.id for item in manifest.contributions.providers}:
                raise PluginRefused(f"Provider {provider.name} still uses this plugin")

    def _load(self, manifest: PluginManifest) -> None:
        contributions = manifest.contributions
        for node in contributions.nodes:
            self.nodes.register(node)
            if node.executable:
                self.handlers[node.type] = self._node_handler(manifest.id, node.type)
        for runtime in contributions.runtimes:
            self.runtimes.register(PluginRuntime(self, manifest.id, runtime))
        for provider in contributions.providers:
            self.providers.extra_types[provider.id] = ProviderType(
                id=provider.id,
                title=provider.title,
                description=provider.description,
                default_endpoint=provider.default_endpoint,
                endpoint_required=provider.default_endpoint is None,
                auth=provider.auth,
                litellm_prefix="openai",
                paid=provider.paid,
            )

    def _unload(self, manifest: PluginManifest) -> None:
        contributions = manifest.contributions
        for node in contributions.nodes:
            self.nodes.unregister(node.type)
            self.handlers.pop(node.type, None)
        for runtime in contributions.runtimes:
            self.runtimes.unregister(runtime.id)
        for provider in contributions.providers:
            self.providers.extra_types.pop(provider.id, None)

    def load_enabled(self) -> None:
        """A broken plugin stays disabled for this run and never stops NEXUS from starting."""
        for plugin in self.all():
            if plugin.enabled and plugin.problem is None:
                manifest = self._manifest(self.directory / plugin.id)
                try:
                    self._check_conflicts(manifest)
                    self._check_dependencies(manifest)
                    self._load(manifest)
                except PluginRefused:
                    continue

    # Execution

    async def call(self, plugin_id: str, kind: str, name: str, payload: dict[str, Any]) -> Any:
        row = self._row(plugin_id)
        if not row.enabled:
            raise PluginRefused(f"Plugin {plugin_id} is disabled")
        manifest = self._read_manifest(row)
        if "filesystem" in row.granted:
            return await self._call(
                row, manifest, self.data_directory / plugin_id, kind, name, payload
            )
        # Without the permission a plugin only gets a scratch folder that dies with the call.
        with tempfile.TemporaryDirectory(dir=self.data_directory) as scratch:
            return await self._call(row, manifest, Path(scratch), kind, name, payload)

    async def _call(self, row, manifest, data_dir, kind, name, payload) -> Any:
        return await call_plugin(
            self.directory / row.id,
            manifest.entry_points.backend,
            data_dir,
            self.settings.data_dir,
            row.granted,
            kind,
            name,
            {**payload, "plugin_config": row.config},
        )

    def _node_handler(self, plugin_id: str, node_type: str) -> NodeHandler:
        async def run(context: NodeContext) -> NodeResult:
            payload = {
                "input": context.input,
                "inputs": context.inputs,
                "config": context.config,
                "workflow_input": context.workflow_input,
            }
            result = await self.call(plugin_id, "node", node_type, payload)
            if isinstance(result, dict) and "__ports__" in result:
                return NodeResult(output=result.get("output"), ports=result["__ports__"])
            return NodeResult(output=result)

        return run
