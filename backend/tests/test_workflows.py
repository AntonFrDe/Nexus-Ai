import json
from pathlib import Path

import pytest
from conftest import authed
from fastapi.testclient import TestClient

from nexus.nodes.catalog import create_node_registry
from nexus.workflows.migrations import UnsupportedSchemaVersion, migrate
from nexus.workflows.schemas import WorkflowGraph
from nexus.workflows.service import parse_import
from nexus.workflows.validation import validate_workflow

EXAMPLES = sorted((Path(__file__).parents[1] / "examples").glob("*.json"))


def n(id_: str, type_: str = "core.logger", **extra) -> dict:
    return {"id": id_, "type": type_, "position": {"x": 0, "y": 0}, **extra}


def e(source: str, target: str, source_port="out", target_port="in", id_=None) -> dict:
    return {
        "id": id_ or f"{source}-{target}",
        "source": source,
        "source_port": source_port,
        "target": target,
        "target_port": target_port,
    }


def codes(nodes: list[dict], edges: list[dict] | None = None) -> set[str]:
    graph = WorkflowGraph.model_validate({"nodes": nodes, "edges": edges or []})
    return {issue.code for issue in validate_workflow(graph, create_node_registry()).issues}


def chain() -> tuple[list[dict], list[dict]]:
    return (
        [n("a", "core.input"), n("b"), n("c", "core.output")],
        [e("a", "b"), e("b", "c")],
    )


def test_valid_chain_has_no_issues():
    assert codes(*chain()) == set()


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_examples_are_valid(path):
    workflow = parse_import(json.loads(path.read_text())).workflow
    report = validate_workflow(workflow, create_node_registry())
    assert report.issues == []


def test_unknown_type_duplicate_ids_and_bad_config():
    assert "unknown_node_type" in codes([n("a", "core.nope")])
    assert "duplicate_node_id" in codes([n("a"), n("a")])
    assert "invalid_config" in codes([n("a", "core.delay")])  # seconds is required
    assert "invalid_config" in codes([n("a", "core.delay", config={"seconds": -1})])
    assert "invalid_runtime" in codes([n("a", runtime={"on_error": "explode"})])


def test_raw_secret_in_a_workflow_is_an_error():
    node = n("a", "core.http_request", config={"url": "http://x", "auth": "sk-live-abc"})
    assert "invalid_config" in codes([node])


def test_permissions_must_be_declared_by_the_type():
    assert "unknown_permission" in codes([n("a", permissions=["shell"])])
    node = n("a", "core.file_reader", config={"path": "x"}, permissions=["filesystem"])
    assert "unknown_permission" not in codes([node])


def test_edge_rules():
    nodes = [n("a"), n("b")]
    assert "edge_unknown_node" in codes(nodes, [e("a", "gone")])
    assert "edge_unknown_port" in codes(nodes, [e("a", "b", source_port="nope")])
    assert "edge_to_self" in codes(nodes, [e("a", "a")])
    assert "duplicate_edge" in codes(nodes, [e("a", "b"), e("a", "b", id_="other")])
    assert "duplicate_edge_id" in codes(nodes, [e("a", "b", id_="x"), e("b", "a", id_="x")])


def test_incompatible_port_types_are_rejected():
    nodes = [n("m", "core.memory", config={"namespace": "x"}), n("j", "core.json_parser")]
    assert "edge_port_type" in codes(nodes, [e("m", "j", source_port="memory")])


def test_required_and_single_input_rules():
    assert "missing_required_input" in codes([n("a")])
    nodes = [n("a"), n("b"), n("c")]
    assert "input_accepts_one" in codes(nodes, [e("a", "c"), e("b", "c")])
    merge = [n("a"), n("b"), n("m", "core.merge")]
    assert "input_accepts_one" not in codes(merge, [e("a", "m"), e("b", "m")])


def test_cycle_needs_a_loop_node():
    assert "unbounded_cycle" in codes([n("a"), n("b")], [e("a", "b"), e("b", "a")])
    nodes = [n("l", "core.loop", config={"mode": "count", "count": 2}), n("b")]
    edges = [e("l", "b", source_port="body"), e("b", "l", target_port="repeat")]
    assert "unbounded_cycle" not in codes(nodes, edges)


def test_structure_warnings_do_not_invalidate():
    graph = WorkflowGraph.model_validate({"nodes": [n("a", "core.annotation")]})
    assert validate_workflow(graph, create_node_registry()).valid
    found = codes([n("a", "core.error_handler"), n("b", "core.error_handler")])
    assert {"no_input", "no_output", "disconnected"} <= found


def test_groups_are_canvas_only_and_parents_are_checked():
    group = n("g", "core.group")
    assert codes([group]) == set()
    assert "invalid_parent" in codes([n("a", parent_id="g")])
    assert "invalid_parent" not in codes([group, n("a", parent_id="g")])


def test_migrations_chain_and_refuse_the_future():
    steps = {1: lambda d: {**d, "a": 1}, 2: lambda d: {**d, "b": 2}}
    assert migrate({"schema_version": 1}, 3, steps) == {"schema_version": 3, "a": 1, "b": 2}
    with pytest.raises(UnsupportedSchemaVersion):
        migrate({"schema_version": 9}, 3, steps)
    with pytest.raises(UnsupportedSchemaVersion):
        migrate({}, 3, steps)
    with pytest.raises(UnsupportedSchemaVersion):
        migrate({"schema_version": 1}, 2, {})


def create(client: TestClient) -> dict:
    return client.post("/api/workflows", json={"name": "Flow"}).json()


def content(document: dict, **changes) -> dict:
    drop = {"id", "created_at", "updated_at"}
    return {key: value for key, value in document.items() if key not in drop} | changes


def test_catalog_endpoint(client):
    catalog = client.get("/api/node-types").json()
    assert catalog["schema_version"] == 1
    assert any(t["type"] == "core.llm_agent" for t in catalog["node_types"])
    assert catalog["runtime_fields"]


def test_invalid_drafts_can_be_saved_but_malformed_documents_cannot(client):
    document = create(client)
    url = f"/api/workflows/{document['id']}"
    draft = content(document, nodes=[n("a", "core.delay")])
    assert client.put(url, json=draft).status_code == 200
    assert client.put(url, json=content(document, nodes=[{"id": "x"}])).status_code == 422
    assert client.put(url, json=content(document, surprise=1)).status_code == 422
    assert client.put(url, json=content(document, schema_version=2)).status_code == 422


def test_validate_endpoint(client):
    report = client.post("/api/workflows/validate", json={"nodes": [n("a", "core.nope")]}).json()
    assert report["valid"] is False
    assert report["issues"][0]["code"] == "unknown_node_type"


def test_save_survives_a_restart(settings):
    with authed(settings) as first:
        document = create(first)
        nodes, edges = chain()
        saved = first.put(
            f"/api/workflows/{document['id']}", json=content(document, nodes=nodes, edges=edges)
        )
        assert saved.status_code == 200
    with authed(settings) as second:
        restored = second.get(f"/api/workflows/{document['id']}").json()
        assert [node["id"] for node in restored["nodes"]] == ["a", "b", "c"]
        assert len(restored["edges"]) == 2


def test_duplicate_export_import(client):
    document = create(client)
    url = f"/api/workflows/{document['id']}"
    client.put(url, json=content(document, nodes=[n("a")], variables={"x": 1}))
    copy = client.post(f"{url}/duplicate").json()
    assert copy["id"] != document["id"] and copy["name"] == "Flow copy"

    exported = client.get(f"{url}/export").json()
    assert exported["format"] == "nexus.workflow"
    assert "id" not in exported["workflow"]
    imported = client.post("/api/workflows/import", json=exported)
    assert imported.status_code == 201
    assert imported.json()["variables"] == {"x": 1}


def test_import_rejects_foreign_and_future_files(client):
    url = "/api/workflows/import"
    assert client.post(url, json={"hello": 1}).status_code == 422
    future = {"format": "nexus.workflow", "workflow": {"name": "x", "schema_version": 99}}
    response = client.post(url, json=future)
    assert response.status_code == 422
    assert "schema 99" in response.json()["detail"]


def test_versions_are_immutable_snapshots(client):
    document = create(client)
    url = f"/api/workflows/{document['id']}"
    client.put(url, json=content(document, nodes=[n("a")]))
    version = client.post(f"{url}/versions", json={"label": "first"}).json()
    assert version["number"] == 1

    client.put(url, json=content(document, nodes=[n("a"), n("b")], name="Changed"))
    assert client.post(f"{url}/versions", json={}).json()["number"] == 2
    assert [v["number"] for v in client.get(f"{url}/versions").json()] == [2, 1]

    restored = client.post(f"{url}/versions/1/restore").json()
    assert restored["name"] == "Flow" and len(restored["nodes"]) == 1
    assert client.post(f"{url}/versions/9/restore").status_code == 404


def test_delete_cascades_to_versions(client):
    document = create(client)
    url = f"/api/workflows/{document['id']}"
    client.post(f"{url}/versions", json={})
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404
    assert client.get(f"{url}/versions").status_code == 404
