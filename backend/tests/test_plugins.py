import json
import time
from pathlib import Path

import pytest
from conftest import authed
from test_execution import e, n, start, wait_for, workflow

from nexus.plugins.manifest import PluginManifest
from nexus.plugins.sandbox import plugin_environment, sandbox_available

EXAMPLES = Path(__file__).parents[2] / "examples" / "plugins"
ID = "com.test.probe"
TYPE = f"{ID}.run"
needs_sandbox = pytest.mark.skipif(not sandbox_available(), reason="macOS sandbox only")


def manifest(**overrides) -> dict:
    return {
        "id": ID,
        "name": "Probe",
        "version": "1.0.0",
        "category": "node",
        "nexus_api": ">=1.0,<2",
        "entry_points": {"backend": "plugin.py"},
        "contributions": {
            "nodes": [
                {
                    "type": TYPE,
                    "title": "Probe",
                    "category": "Plugins",
                    "description": "",
                    "icon": "box",
                    "inputs": [{"id": "in", "label": "In"}],
                    "outputs": [{"id": "out", "label": "Out"}],
                }
            ]
        },
        **overrides,
    }


def package(root: Path, code: str, **overrides) -> Path:
    folder = root / f"pkg-{overrides.get('version', '1')}-{abs(hash(code))}"
    folder.mkdir(parents=True)
    (folder / "nexus-plugin.json").write_text(json.dumps(manifest(**overrides)))
    (folder / "plugin.py").write_text(code)
    return folder


def install(client, folder: Path, granted: list[str] | None = None) -> dict:
    response = client.post("/api/plugins/install", json={"path": str(folder)})
    assert response.status_code == 201, response.text
    plugin = response.json()
    enabled = client.post(f"/api/plugins/{plugin['id']}/enable", json={"granted": granted or []})
    assert enabled.status_code == 200, enabled.text
    return enabled.json()


def run_node(client, type_: str, value="x", config=None, port="out", timeout=20) -> dict:
    node = {
        "id": "p",
        "type": type_,
        "position": {"x": 0, "y": 0},
        "config": config or {},
    }
    nodes = [n("in", "input"), node, n("o", "output")]
    edges = [e("in", "p"), e("p", "o", port)]
    execution = start(client, workflow(client, nodes, edges), value)
    return wait_for(client, execution["id"], "COMPLETED", "FAILED", timeout=timeout)


ATTACK = """
import os, socket, subprocess
from nexus_plugin import node

def attempt(action):
    try:
        action()
    except BaseException as error:
        return "blocked"
    return "ALLOWED"

@node("com.test.probe.run")
def run(request):
    secret = request["input"]
    return {
        "read_master_key": attempt(lambda: open(secret + "/master.key").read()),
        "read_token": attempt(lambda: open(secret + "/api-token").read()),
        "read_database": attempt(lambda: open(secret + "/nexus.db", "rb").read(1)),
        "write_outside": attempt(lambda: open(secret + "/planted", "w").write("x")),
        "network": attempt(lambda: socket.create_connection(("127.0.0.1", 11434), 1)),
        "shell": attempt(lambda: subprocess.run(["/bin/ls"], check=True)),
        "environment": sorted(os.environ),
        "write_own_folder": attempt(lambda: open("scratch", "w").write("x")),
    }
"""


@needs_sandbox
def test_a_hostile_plugin_cannot_reach_secrets_network_or_shell(client, settings, tmp_path):
    client.put("/api/secrets/a", json={"value": "secret"})
    (settings.data_dir / "api-token").write_text("token")
    install(client, package(tmp_path / "src", ATTACK))
    detail = run_node(client, TYPE, str(settings.data_dir.resolve()))
    assert detail["status"] == "COMPLETED", detail["error"]
    report = detail["output"]["result"]
    for name in ("read_master_key", "read_token", "read_database", "write_outside", "network"):
        assert report[name] == "blocked", name
    assert report["shell"] == "blocked"
    assert report["write_own_folder"] == "ALLOWED"
    assert "NEXUS_DATA_DIR" not in report["environment"]
    assert not (settings.data_dir / "planted").exists()


@needs_sandbox
def test_granted_permissions_open_only_that_access(client, settings, tmp_path):
    install(client, package(tmp_path / "src", ATTACK, permissions=["shell"]), ["shell"])
    detail = run_node(client, TYPE, str(settings.data_dir.resolve()))
    report = detail["output"]["result"]
    assert report["shell"] == "ALLOWED"
    assert report["network"] == "blocked"
    assert report["read_master_key"] == "blocked"


@needs_sandbox
def test_filesystem_permission_gives_a_lasting_private_folder(client, tmp_path):
    code = """
import os
from nexus_plugin import node
@node("com.test.probe.run")
def run(request):
    present = os.path.exists("note")
    open("note", "w").write("x")
    return present
"""
    install(client, package(tmp_path / "src", code, permissions=["filesystem"]), ["filesystem"])
    assert run_node(client, TYPE)["output"]["result"] is False
    assert run_node(client, TYPE)["output"]["result"] is True


def test_only_named_environment_variables_reach_a_plugin(monkeypatch, tmp_path):
    monkeypatch.setenv("VISIBLE", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    environment = plugin_environment(["env:VISIBLE"], tmp_path)
    assert environment["VISIBLE"] == "1"
    assert "ANTHROPIC_API_KEY" not in environment


@needs_sandbox
def test_crash_garbage_and_hang_fail_the_node_not_the_app(client, tmp_path):
    crash = """
from nexus_plugin import node
@node("com.test.probe.run")
def r(q):
    raise ValueError("boom")
"""
    install(client, package(tmp_path / "a", crash))
    detail = run_node(client, TYPE)
    assert detail["status"] == "FAILED"
    assert "boom" in detail["error"]
    assert client.get("/api/health").status_code == 200


@needs_sandbox
def test_a_stuck_plugin_is_killed(client, tmp_path, monkeypatch):
    import nexus.plugins.service as service

    original = service.call_plugin

    async def short(*args, **kwargs):
        return await original(*args, timeout=0.5, **kwargs)

    monkeypatch.setattr(service, "call_plugin", short)
    code = """
import time
from nexus_plugin import node
@node("com.test.probe.run")
def r(q):
    time.sleep(60)
"""
    install(client, package(tmp_path / "a", code))
    started = time.monotonic()
    detail = run_node(client, TYPE)
    assert detail["status"] == "FAILED"
    assert "did not answer" in detail["error"]
    assert time.monotonic() - started < 10


def test_printing_does_not_corrupt_the_reply(client, tmp_path):
    if not sandbox_available():
        pytest.skip("macOS sandbox only")
    code = """
from nexus_plugin import node
@node("com.test.probe.run")
def r(q):
    print("noise")
    return 1
"""
    install(client, package(tmp_path / "a", code))
    assert run_node(client, TYPE)["output"]["result"] == 1


@pytest.mark.parametrize(
    "change",
    [
        {"id": "Bad Id"},
        {"version": "not a version"},
        {"nexus_api": "nonsense"},
        {"permissions": ["root"]},
        {"permissions": ["credentials"]},
        {"category": "unknown"},
        {"entry_points": {"backend": "../escape.py"}},
        {"entry_points": {"backend": "/etc/passwd"}},
        {"surprise": 1},
    ],
)
def test_bad_manifests_are_refused(client, tmp_path, change):
    folder = package(tmp_path, "", **change)
    response = client.post("/api/plugins/install", json={"path": str(folder)})
    assert response.status_code == 409
    assert "Invalid manifest" in response.json()["detail"]


def test_a_plugin_cannot_claim_core_names(client, tmp_path):
    body = manifest()
    body["contributions"]["nodes"][0]["type"] = "core.input"
    folder = tmp_path / "x"
    folder.mkdir()
    (folder / "nexus-plugin.json").write_text(json.dumps(body))
    (folder / "plugin.py").write_text("")
    assert client.post("/api/plugins/install", json={"path": str(folder)}).status_code == 409


def test_missing_files_and_symlinks_are_refused(client, tmp_path):
    folder = package(tmp_path, "x")
    (folder / "plugin.py").unlink()
    assert client.post("/api/plugins/install", json={"path": str(folder)}).status_code == 409
    other = package(tmp_path, "y")
    (other / "link").symlink_to("/etc/passwd")
    response = client.post("/api/plugins/install", json={"path": str(other)})
    assert "symbolic" in response.json()["detail"]


def test_installing_runs_no_plugin_code(client, tmp_path):
    marker = tmp_path / "ran"
    code = f'open({str(marker)!r}, "w").write("x")\n'
    response = client.post("/api/plugins/install", json={"path": str(package(tmp_path, code))})
    assert response.status_code == 201
    assert response.json()["enabled"] is False
    assert not marker.exists()


def test_enabling_needs_every_permission_accepted(client, tmp_path):
    folder = package(tmp_path, "", permissions=["network", "env:FOO"])
    client.post("/api/plugins/install", json={"path": str(folder)})
    url = f"/api/plugins/{ID}/enable"
    assert client.post(url, json={"granted": []}).status_code == 409
    assert client.post(url, json={"granted": ["network"]}).status_code == 409
    assert client.post(url, json={"granted": ["network", "env:FOO"]}).status_code == 200


def test_incompatible_api_is_refused(client, tmp_path):
    client.post(
        "/api/plugins/install",
        json={"path": str(package(tmp_path, "", nexus_api=">=9"))},
    )
    assert client.get("/api/plugins").json()[0]["compatible"] is False
    response = client.post(f"/api/plugins/{ID}/enable", json={"granted": []})
    assert "NEXUS API" in response.json()["detail"]


def test_updates_must_be_newer_and_new_permissions_need_consent(client, tmp_path):
    install(client, package(tmp_path / "a", "#"))
    same = client.post("/api/plugins/install", json={"path": str(package(tmp_path / "b", "#2"))})
    assert same.status_code == 409
    newer = package(tmp_path / "c", "#3", version="2.0.0", permissions=["network"])
    updated = client.post("/api/plugins/install", json={"path": str(newer)}).json()
    assert updated["version"] == "2.0.0"
    assert updated["enabled"] is False
    assert updated["granted"] == []


def dependent(root: Path, required: str = ">=1.0") -> Path:
    folder = root / "dep"
    folder.mkdir(parents=True)
    body = {
        "id": "com.test.dependent",
        "name": "Dependent",
        "version": "1.0.0",
        "category": "panel",
        "nexus_api": ">=1.0",
        "dependencies": {ID: required},
    }
    (folder / "nexus-plugin.json").write_text(json.dumps(body))
    return folder


def test_dependencies_are_checked_in_both_directions(client, tmp_path):
    client.post("/api/plugins/install", json={"path": str(dependent(tmp_path))})
    url = "/api/plugins/com.test.dependent/enable"
    assert "Needs plugin" in client.post(url, json={"granted": []}).json()["detail"]
    install(client, package(tmp_path / "a", "#"))
    assert client.post(url, json={"granted": []}).status_code == 200
    assert client.post(f"/api/plugins/{ID}/disable").status_code == 409
    assert client.delete(f"/api/plugins/{ID}").status_code == 409


def test_wrong_dependency_version_is_refused(client, tmp_path):
    install(client, package(tmp_path / "a", "#"))
    client.post("/api/plugins/install", json={"path": str(dependent(tmp_path, ">=2"))})
    response = client.post("/api/plugins/com.test.dependent/enable", json={"granted": []})
    assert "found 1.0.0" in response.json()["detail"]


def test_disabled_nodes_cannot_run_and_uninstall_removes_files(client, settings, tmp_path):
    install(client, package(tmp_path / "a", "#"))
    assert any(t["type"] == TYPE for t in client.get("/api/node-types").json()["node_types"])
    client.post(f"/api/plugins/{ID}/disable")
    assert not any(t["type"] == TYPE for t in client.get("/api/node-types").json()["node_types"])
    nodes = [n("in", "input"), {"id": "p", "type": TYPE, "position": {"x": 0, "y": 0}}]
    workflow_id = workflow(client, nodes, [e("in", "p")])
    assert client.post(f"/api/workflows/{workflow_id}/executions", json={}).status_code == 422
    assert client.delete(f"/api/plugins/{ID}").status_code == 204
    assert not (settings.data_dir / "plugins" / ID).exists()


def test_enabled_plugins_return_after_a_restart(settings, tmp_path):
    with authed(settings) as first:
        install(first, package(tmp_path / "a", "#"))
    with authed(settings) as second:
        types = second.get("/api/node-types").json()["node_types"]
        assert any(t["type"] == TYPE for t in types)


def test_a_damaged_plugin_does_not_stop_startup(settings, tmp_path):
    with authed(settings) as first:
        install(first, package(tmp_path / "a", "#"))
    (settings.data_dir / "plugins" / ID / "nexus-plugin.json").write_text("{broken")
    with authed(settings) as second:
        assert second.get("/api/health").status_code == 200
        assert "Invalid manifest" in second.get("/api/plugins").json()[0]["problem"]


def example(client, name: str) -> dict:
    return install(client, EXAMPLES / name)


def test_example_manifests_are_valid():
    for path in EXAMPLES.glob("*/nexus-plugin.json"):
        PluginManifest.model_validate_json(path.read_bytes())
    assert len(list(EXAMPLES.glob("*/nexus-plugin.json"))) == 4


@needs_sandbox
def test_example_node_routes_and_uses_plugin_config(client):
    example(client, "word-count")
    type_ = "com.nexus-examples.word-count.count"
    detail = run_node(client, type_, "one two three", {"unit": "mots"}, port="short")
    assert detail["output"]["result"] == {"count": 3, "unit": "mots"}
    client.put(
        "/api/plugins/com.nexus-examples.word-count/config", json={"config": {"long_after": 2}}
    )
    detail = run_node(client, type_, "one two three", port="short")
    assert detail["output"] == {}
    invalid = client.put(
        "/api/plugins/com.nexus-examples.word-count/config", json={"config": {"nope": 1}}
    )
    assert invalid.status_code == 409


@needs_sandbox
def test_example_tool(client):
    example(client, "slugify-tool")
    detail = run_node(client, "com.nexus-examples.slugify-tool.slugify", "Été à Paris !")
    assert detail["output"]["result"] == "ete-a-paris"


def test_example_panel_is_served_with_a_locked_down_policy(client):
    example(client, "clock-panel")
    panels = client.get("/api/plugins/panels").json()
    assert panels[0]["title"] == "Session Clock"
    url = f"/api/plugins/{panels[0]['plugin_id']}/panels/{panels[0]['id']}"
    page = client.get(url)
    assert page.status_code == 200
    assert "sandbox allow-scripts" in page.headers["content-security-policy"]
    assert "allow-same-origin" not in page.headers["content-security-policy"]
    assert "connect-src 'none'" in page.headers["content-security-policy"]
    assert client.get(url.replace("clock", "nope")).status_code == 404
    client.post(f"/api/plugins/{panels[0]['plugin_id']}/disable")
    assert client.get(url).status_code == 404


def test_example_provider_adds_a_type_and_stays_until_unused(client):
    plugin = example(client, "openai-preset")
    type_id = "com.nexus-examples.openai-preset.gateway"
    assert type_id in [t["id"] for t in client.get("/api/provider-types").json()]
    provider = client.post("/api/providers", json={"type": type_id, "name": "Gate"}).json()
    assert provider["endpoint"] == "http://127.0.0.1:4000/v1"
    assert client.post(f"/api/plugins/{plugin['id']}/disable").status_code == 409
    client.delete(f"/api/providers/{provider['id']}")
    assert client.post(f"/api/plugins/{plugin['id']}/disable").status_code == 200
    assert type_id not in [t["id"] for t in client.get("/api/provider-types").json()]


@needs_sandbox
def test_plugin_runtime_runs_an_agent(client, tmp_path):
    body = manifest(category="runtime")
    body["contributions"] = {"runtimes": [{"id": f"{ID}.echo", "title": "Echo"}]}
    folder = tmp_path / "rt"
    folder.mkdir()
    (folder / "nexus-plugin.json").write_text(json.dumps(body))
    (folder / "plugin.py").write_text(
        'from nexus_plugin import runtime\n@runtime("com.test.probe.echo")\n'
        'def go(q): return {"text": "echo " + q["prompt"]}\n'
    )
    install(client, folder)
    agent = client.post("/api/agents", json={"name": "Echo"}).json()
    definition = {"system_prompt": "x", "runtime": f"{ID}.echo", "model": "any"}
    client.patch(f"/api/agents/{agent['id']}", json={"definition": definition})
    nodes = [n("in", "input"), n("c", "custom_agent", agent_id=agent["id"]), n("o", "output")]
    execution = start(client, workflow(client, nodes, [e("in", "c"), e("c", "o")]), "hi")
    detail = wait_for(client, execution["id"], "COMPLETED", timeout=20)
    assert detail["output"] == {"result": "echo hi"}
