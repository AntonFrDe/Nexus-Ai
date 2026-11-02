import json
import logging
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER = logging.getLogger("nexus")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "event": record.getMessage(),
            **getattr(record, "fields", {}),
        }
        return json.dumps(entry)


def attach_log_file(data_dir: Path) -> logging.Handler:
    """One JSON object per line. Callers log ids and statuses, never prompts or outputs."""
    directory = data_dir / "logs"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    handler = RotatingFileHandler(
        directory / "nexus.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(JsonFormatter())
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    return handler


def log_event(event: str, **fields: object) -> None:
    LOGGER.info(event, extra={"fields": fields})
