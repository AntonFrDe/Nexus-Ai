from collections.abc import Iterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from nexus.core.config import Settings

BACKEND_ROOT = Path(__file__).resolve().parents[3]


class Base(DeclarativeBase):
    pass


def sqlite_url(settings: Settings) -> str:
    return f"sqlite:///{settings.database_path}"


def create_db_engine(settings: Settings) -> Engine:
    settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    engine = create_engine(sqlite_url(settings), connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _configure(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def run_migrations(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", sqlite_url(settings).replace("%", "%%"))
    command.upgrade(config, "head")


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a session committed on success and rolled back on any error."""
    with factory() as session, session.begin():
        yield session
