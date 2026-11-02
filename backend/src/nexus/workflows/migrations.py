from collections.abc import Callable, Mapping
from typing import Any

Document = dict[str, Any]
Migration = Callable[[Document], Document]

CURRENT_SCHEMA_VERSION = 1

# Maps a version to the pure function upgrading a document to the next version.
MIGRATIONS: dict[int, Migration] = {}


class UnsupportedSchemaVersion(ValueError):
    pass


def migrate(
    document: Document,
    current: int = CURRENT_SCHEMA_VERSION,
    migrations: Mapping[int, Migration] = MIGRATIONS,
) -> Document:
    version = document.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise UnsupportedSchemaVersion("schema_version must be an integer")
    if version > current:
        raise UnsupportedSchemaVersion(
            f"Workflow uses schema {version}; this NEXUS supports up to {current}"
        )
    while version < current:
        step = migrations.get(version)
        if step is None:
            raise UnsupportedSchemaVersion(f"No migration from schema {version}")
        document = step(dict(document))
        version += 1
        document["schema_version"] = version
    return document
