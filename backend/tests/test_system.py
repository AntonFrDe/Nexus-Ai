from fastapi.testclient import TestClient

from nexus.core.config import Settings
from nexus.main import create_app


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_settings_round_trip(client):
    assert client.get("/api/settings/active").status_code == 404
    assert client.put("/api/settings/active", json={"value": "abc"}).status_code == 200
    assert client.get("/api/settings/active").json() == {"value": "abc"}


def test_defaults_bind_to_loopback_only():
    assert Settings().host == "127.0.0.1"


def test_unknown_host_header_is_rejected(settings):
    settings.allowed_hosts = ["localhost"]
    with TestClient(create_app(settings), base_url="http://evil.example") as client:
        assert client.get("/api/health").status_code == 400


def test_api_requires_the_launch_token(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/workspaces").status_code == 401
        headers = {"Authorization": "Bearer wrong"}
        assert client.get("/api/workspaces", headers=headers).status_code == 401
        assert client.get("/api/health").status_code == 200
        headers = {"Authorization": "Bearer test-token"}
        assert client.get("/api/workspaces", headers=headers).status_code == 200


def test_each_launch_writes_a_private_token(settings):
    settings.api_token = None
    with TestClient(create_app(settings)):
        path = settings.data_dir / "api-token"
        first = path.read_text()
        assert path.stat().st_mode & 0o777 == 0o600
    with TestClient(create_app(settings)):
        assert path.read_text() != first
