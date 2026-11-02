import os
import secrets
from pathlib import Path

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

TOKEN_FILE = "api-token"
PUBLIC_PATHS = {"/api/health"}


def issue_token(data_dir: Path) -> str:
    """Creates this launch's token, readable only by the owner of the data directory."""
    token = secrets.token_urlsafe(32)
    path = data_dir / TOKEN_FILE
    temporary = path.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as file:
        file.write(token)
    temporary.replace(path)
    return token


class TokenAuthMiddleware:
    """Requires the launch token on the API. Pure ASGI so event streams are never buffered."""

    def __init__(self, app: ASGIApp, state) -> None:
        self.app = app
        self.state = state

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return
        supplied = Headers(scope=scope).get("authorization", "")
        expected = f"Bearer {self.state.api_token}"
        if not secrets.compare_digest(supplied.encode(), expected.encode()):
            response = JSONResponse({"detail": "Missing or invalid API token"}, status_code=401)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
