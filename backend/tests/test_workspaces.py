from conftest import authed
from fastapi.testclient import TestClient

LAYOUT = {"grid": {"root": {}}, "panels": {"a": {"id": "a"}}, "activeGroup": "1"}


def first_id(client: TestClient) -> str:
    return client.get("/api/workspaces").json()[0]["id"]


def test_first_launch_seeds_the_six_default_workspaces(client):
    presets = [w["preset"] for w in client.get("/api/workspaces").json()]
    assert presets == [
        "workflow-builder",
        "agent-development",
        "debug-studio",
        "execution-monitor",
        "analytics",
        "custom",
    ]


def test_create_then_read(client):
    created = client.post("/api/workspaces", json={"name": "Mine", "preset": "custom"})
    assert created.status_code == 201
    fetched = client.get(f"/api/workspaces/{created.json()['id']}").json()
    assert fetched["name"] == "Mine"
    assert fetched["layout"] is None


def test_layout_and_state_survive_a_restart(settings):
    with authed(settings) as first:
        workspace_id = first_id(first)
        response = first.patch(
            f"/api/workspaces/{workspace_id}",
            json={"layout": LAYOUT, "panel_states": {"notes": {"text": "hi"}}},
        )
        assert response.status_code == 200
    with authed(settings) as second:
        restored = second.get(f"/api/workspaces/{workspace_id}").json()
        assert restored["layout"] == LAYOUT
        assert restored["panel_states"] == {"notes": {"text": "hi"}}
        assert len(second.get("/api/workspaces").json()) == 6  # no re-seed


def test_partial_update_leaves_other_fields_alone(client):
    workspace_id = first_id(client)
    client.patch(f"/api/workspaces/{workspace_id}", json={"layout": LAYOUT})
    client.patch(f"/api/workspaces/{workspace_id}", json={"name": "Renamed"})
    workspace = client.get(f"/api/workspaces/{workspace_id}").json()
    assert (workspace["name"], workspace["layout"]) == ("Renamed", LAYOUT)


def test_layout_can_be_cleared_to_reset_to_preset(client):
    workspace_id = first_id(client)
    client.patch(f"/api/workspaces/{workspace_id}", json={"layout": LAYOUT})
    client.patch(f"/api/workspaces/{workspace_id}", json={"layout": None})
    assert client.get(f"/api/workspaces/{workspace_id}").json()["layout"] is None


def test_rejects_malformed_layout_unknown_fields_and_empty_names(client):
    workspace_id = first_id(client)
    url = f"/api/workspaces/{workspace_id}"
    assert client.patch(url, json={"layout": {"nope": 1}}).status_code == 422
    assert client.patch(url, json={"surprise": 1}).status_code == 422
    assert client.patch(url, json={"name": ""}).status_code == 422
    assert client.patch(url, json={"name": None}).status_code == 422
    assert client.post("/api/workspaces", json={"name": ""}).status_code == 422


def test_rejects_oversized_documents(client):
    huge = {"text": "x" * 2_000_001}
    response = client.patch(f"/api/workspaces/{first_id(client)}", json={"panel_states": huge})
    assert response.status_code == 422


def test_duplicate_copies_content_under_a_new_identity(client):
    workspace_id = first_id(client)
    client.patch(f"/api/workspaces/{workspace_id}", json={"layout": LAYOUT})
    copy = client.post(f"/api/workspaces/{workspace_id}/duplicate", json={}).json()
    assert copy["id"] != workspace_id
    assert copy["name"] == "Workflow Builder copy"
    assert copy["layout"] == LAYOUT


def test_export_import_round_trip(client):
    workspace_id = first_id(client)
    client.patch(f"/api/workspaces/{workspace_id}", json={"layout": LAYOUT})
    document = client.get(f"/api/workspaces/{workspace_id}/export").json()
    assert document["format"] == "nexus.workspace"
    assert "id" not in document["workspace"]
    imported = client.post("/api/workspaces/import", json=document)
    assert imported.status_code == 201
    assert imported.json()["id"] != workspace_id
    assert imported.json()["layout"] == LAYOUT


def test_import_rejects_foreign_files_and_future_versions(client):
    url = "/api/workspaces/import"
    assert client.post(url, json={"hello": "world"}).status_code == 422
    body = {"format": "nexus.workspace", "schema_version": 2, "workspace": {"name": "x"}}
    assert client.post(url, json=body).status_code == 422


def test_delete_and_last_workspace_protection(client):
    ids = [w["id"] for w in client.get("/api/workspaces").json()]
    for workspace_id in ids[:-1]:
        assert client.delete(f"/api/workspaces/{workspace_id}").status_code == 204
    assert client.delete(f"/api/workspaces/{ids[-1]}").status_code == 409
    assert client.get(f"/api/workspaces/{ids[0]}").status_code == 404
