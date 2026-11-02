import sqlite3

from conftest import authed
from cryptography.fernet import Fernet

from nexus.core.config import Settings
from nexus.secrets.service import load_master_key

VALUE = "sk-live-super-secret"


def test_secrets_are_write_only_over_the_api(client):
    assert client.put("/api/secrets/openai.main", json={"value": VALUE}).status_code == 204
    listing = client.get("/api/secrets")
    assert [item["name"] for item in listing.json()] == ["openai.main"]
    assert VALUE not in listing.text
    assert client.get("/api/secrets/openai.main").status_code in (404, 405)


def test_value_is_encrypted_at_rest_and_key_kept_apart(client, settings):
    client.put("/api/secrets/a", json={"value": VALUE})
    assert VALUE.encode() not in settings.database_path.read_bytes()
    connection = sqlite3.connect(settings.database_path)
    stored = connection.execute("select ciphertext from secrets").fetchone()[0]
    connection.close()
    assert VALUE.encode() not in stored
    key_path = settings.data_dir / "master.key"
    assert key_path.stat().st_mode & 0o777 == 0o600
    assert key_path.read_bytes() not in settings.database_path.read_bytes()


def test_secret_survives_restart_and_can_be_replaced_or_deleted(settings):
    with authed(settings) as first:
        first.put("/api/secrets/a", json={"value": "one"})
    with authed(settings) as second:
        assert second.app.state.secrets.resolve("a") == "one"
        second.put("/api/secrets/a", json={"value": "two"})
        assert second.app.state.secrets.resolve("a") == "two"
        assert second.delete("/api/secrets/a").status_code == 204
        assert second.delete("/api/secrets/a").status_code == 404


def test_names_are_restricted_and_extra_fields_refused(client):
    assert client.put("/api/secrets/bad name", json={"value": "x"}).status_code == 422
    assert client.put("/api/secrets/a", json={"value": ""}).status_code == 422
    assert client.put("/api/secrets/a", json={"value": "x", "y": 1}).status_code == 422


def test_validation_errors_never_echo_a_value(client):
    response = client.put("/api/secrets/a", json={"value": VALUE, "extra": 1})
    assert VALUE not in response.text


def test_a_changed_master_key_reports_rather_than_returns_garbage(settings):
    with authed(settings) as first:
        first.put("/api/secrets/a", json={"value": "one"})
    (settings.data_dir / "master.key").write_bytes(Fernet.generate_key())
    with authed(settings) as second:
        provider = second.post(
            "/api/providers",
            json={"type": "openai", "name": "o", "secret_name": "a"},
        ).json()
        result = second.post(f"/api/providers/{provider['id']}/test").json()
        assert result["ok"] is False
        assert "master key" in result["message"]


def test_file_backend_is_reported_and_stable(tmp_path):
    settings = Settings(data_dir=tmp_path, secret_backend="file")
    first, backend = load_master_key(settings)
    assert backend == "file"
    assert load_master_key(settings)[0] == first


def test_secrets_are_not_part_of_workflow_or_workspace_exports(client):
    client.put("/api/secrets/a", json={"value": VALUE})
    workspace = client.get("/api/workspaces").json()[0]["id"]
    assert VALUE not in client.get(f"/api/workspaces/{workspace}/export").text
