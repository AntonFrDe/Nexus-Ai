from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, overridable through NEXUS_* environment variables."""

    model_config = SettingsConfigDict(env_prefix="NEXUS_")

    data_dir: Path = Path.home() / ".nexus"
    host: str = "127.0.0.1"
    port: int = 8000
    # Rejecting unknown Host headers blocks DNS-rebinding against the local API.
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]
    # Fixed only by tests; otherwise each launch issues its own token.
    api_token: str | None = None
    max_concurrent_executions: int = 4
    # auto uses the OS keychain when there is one, otherwise a private file.
    secret_backend: Literal["auto", "keychain", "file"] = "auto"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "nexus.db"

    @property
    def checkpoints_path(self) -> Path:
        return self.data_dir / "checkpoints.db"
