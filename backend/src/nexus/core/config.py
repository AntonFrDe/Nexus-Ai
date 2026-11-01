from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, overridable through NEXUS_* environment variables."""

    model_config = SettingsConfigDict(env_prefix="NEXUS_")

    data_dir: Path = Path.home() / ".nexus"
    host: str = "127.0.0.1"
    port: int = 8000
    # Rejecting unknown Host headers blocks DNS-rebinding against the local API.
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]

    @property
    def database_path(self) -> Path:
        return self.data_dir / "nexus.db"
