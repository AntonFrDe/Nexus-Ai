from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from nexus.core.db import session_scope


def get_session(request: Request) -> Iterator[Session]:
    yield from session_scope(request.app.state.session_factory)
