from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from nexus.core.db import Base


def _uuid() -> str:
    return str(uuid4())


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    type: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(120), unique=True)
    endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # A reference to the secrets service; the key itself is never stored here.
    secret_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    timeout_seconds: Mapped[float] = mapped_column(Float, default=60)
    rate_limit_rpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Model(Base):
    __tablename__ = "models"
    __table_args__ = (UniqueConstraint("provider_id", "model_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id", ondelete="CASCADE"))
    model_id: Mapped[str] = mapped_column(String(200))
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capabilities: Mapped[dict[str, bool]] = mapped_column(JSON)
    # Manual corrections, kept apart so that rediscovery does not erase them.
    capability_overrides: Mapped[dict[str, bool]] = mapped_column(JSON, default=dict)
    input_cost_per_mtok: Mapped[float | None] = mapped_column(Float, nullable=True)
    output_cost_per_mtok: Mapped[float | None] = mapped_column(Float, nullable=True)
    defaults: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(16), default="manual")
    last_test: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
