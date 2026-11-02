import re
from typing import Annotated, Self

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from nexus.nodes.spec import FieldSpec, NodeType

MANIFEST_FILE = "nexus-plugin.json"
API_VERSION = "1.0.0"
# Permissions a plugin may hold. Secrets and other plugins have no broker yet, so asking for
# them is refused rather than silently ignored.
PLAIN_PERMISSIONS = {"filesystem", "network", "shell"}
UNAVAILABLE_PERMISSIONS = {"credentials", "plugins"}
ENV_PERMISSION = re.compile(r"^env:[A-Z][A-Z0-9_]{0,63}$")
PluginId = Annotated[str, Field(pattern=r"^[a-z0-9]+(\.[a-z0-9-]+)+$", max_length=120)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EntryPoints(Strict):
    backend: str | None = None


class PanelContribution(Strict):
    id: str
    title: str = Field(min_length=1, max_length=80)
    description: str = ""
    category: str = "Plugins"
    page: str


class RuntimeContribution(Strict):
    id: str
    title: str = Field(min_length=1, max_length=80)
    description: str = ""


class ProviderContribution(Strict):
    """Data only: an OpenAI-style endpoint preset. No plugin code handles provider keys."""

    id: str
    title: str = Field(min_length=1, max_length=80)
    description: str = ""
    default_endpoint: str | None = Field(default=None, pattern=r"^https?://")
    auth: str = Field(default="optional", pattern=r"^(none|optional|api_key)$")
    paid: bool = True


class Contributions(Strict):
    nodes: list[NodeType] = Field(default_factory=list)
    panels: list[PanelContribution] = Field(default_factory=list)
    runtimes: list[RuntimeContribution] = Field(default_factory=list)
    providers: list[ProviderContribution] = Field(default_factory=list)


def _inside_package(path: str) -> str:
    parts = path.split("/")
    if path.startswith("/") or "\\" in path or ".." in parts or not path.strip():
        raise ValueError(f"{path} must be a relative path inside the plugin")
    return path


class PluginManifest(Strict):
    id: PluginId
    name: str = Field(min_length=1, max_length=120)
    version: str
    description: str = ""
    author: str = ""
    category: str = Field(pattern=r"^(panel|node|provider|tool|runtime|integration)$")
    nexus_api: str
    entry_points: EntryPoints = Field(default_factory=EntryPoints)
    dependencies: dict[str, str] = Field(default_factory=dict)
    permissions: list[str] = Field(default_factory=list)
    config: list[FieldSpec] = Field(default_factory=list)
    contributions: Contributions = Field(default_factory=Contributions)

    @field_validator("version")
    @classmethod
    def _version(cls, value: str) -> str:
        try:
            Version(value)
        except InvalidVersion as error:
            raise ValueError(f"Invalid version: {value}") from error
        return value

    @field_validator("nexus_api")
    @classmethod
    def _api(cls, value: str) -> str:
        try:
            SpecifierSet(value)
        except InvalidSpecifier as error:
            raise ValueError(f"Invalid version range: {value}") from error
        return value

    @field_validator("dependencies")
    @classmethod
    def _dependencies(cls, value: dict[str, str]) -> dict[str, str]:
        for spec in value.values():
            try:
                SpecifierSet(spec)
            except InvalidSpecifier as error:
                raise ValueError(f"Invalid version range: {spec}") from error
        return value

    @field_validator("permissions")
    @classmethod
    def _permissions(cls, value: list[str]) -> list[str]:
        for permission in value:
            if permission in UNAVAILABLE_PERMISSIONS:
                raise ValueError(f"The {permission} permission is not available yet")
            if permission not in PLAIN_PERMISSIONS and not ENV_PERMISSION.match(permission):
                raise ValueError(f"Unknown permission: {permission}")
        return value

    @model_validator(mode="after")
    def _ownership(self) -> Self:
        """Everything lives under the plugin's own id, so a plugin cannot shadow core items."""
        prefix = f"{self.id}."
        owned = [
            *(item.type for item in self.contributions.nodes),
            *(item.id for item in self.contributions.panels),
            *(item.id for item in self.contributions.runtimes),
            *(item.id for item in self.contributions.providers),
        ]
        for name in owned:
            if not name.startswith(prefix):
                raise ValueError(f"{name} must start with {prefix}")
        if len(owned) != len(set(owned)):
            raise ValueError("Contribution ids must be unique")
        code_needed = self.contributions.runtimes or any(
            node.executable for node in self.contributions.nodes
        )
        if code_needed and not self.entry_points.backend:
            raise ValueError("Nodes and runtimes need a backend entry point")
        if self.entry_points.backend:
            _inside_package(self.entry_points.backend)
        for panel in self.contributions.panels:
            _inside_package(panel.page)
        return self
