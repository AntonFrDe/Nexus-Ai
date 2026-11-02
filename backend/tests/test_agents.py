from dataclasses import dataclass

import pytest
from fake_provider import API_KEY, start_fake_provider
from test_execution import e, n, start, wait_for, workflow

from nexus.runtimes.antigravity import build_config
from nexus.runtimes.base import (
    AgentRequest,
    AgentResult,
    RuntimeAdapter,
    RuntimeCapabilities,
    UnsupportedCapability,
)
from nexus.runtimes.claude_sdk import ClaudeAgentRuntime, build_options
from nexus.runtimes.native import NativeRuntime


@pytest.fixture
def fake():
    server = start_fake_provider()
    yield server
    server.shutdown()


def base(server) -> str:
    return f"http://127.0.0.1:{server.server_address[1]}"


def local_model(client, fake, name="Local") -> str:
    provider = client.post(
        "/api/providers", json={"type": "ollama", "name": name, "endpoint": base(fake)}
    ).json()
    client.post(f"/api/providers/{provider['id']}/discover")
    return f"{name}/local-coder:latest"


def paid_model(client, fake) -> str:
    client.put("/api/secrets/hosted", json={"value": API_KEY})
    provider = client.post(
        "/api/providers",
        json={
            "type": "openai_compatible",
            "name": "Hosted",
            "endpoint": f"{base(fake)}/v1",
            "secret_name": "hosted",
        },
    ).json()
    client.post(f"/api/providers/{provider['id']}/discover")
    return "Hosted/hosted-model"


def agent_flow(client, node: dict, value="hello") -> dict:
    nodes = [n("in", "input"), node, n("out", "output")]
    edges = [e("in", node["id"]), e(node["id"], "out")]
    return start(client, workflow(client, nodes, edges), value)


def test_agent_create_from_template_clone_and_versions(client):
    templates = client.get("/api/agent-templates").json()
    assert {item["id"] for item in templates} >= {"planner", "reviewer", "extractor"}
    agent = client.post("/api/agents", json={"name": "Plan", "template": "planner"}).json()
    assert agent["definition"]["role"] == "Planning"
    assert agent["version"] == 1
    url = f"/api/agents/{agent['id']}"

    changed = {**agent["definition"], "system_prompt": "New"}
    updated = client.patch(url, json={"definition": changed}).json()
    assert updated["version"] == 2
    assert [v["number"] for v in client.get(f"{url}/versions").json()] == [2, 1]

    restored = client.post(f"{url}/versions/1/restore").json()
    assert restored["version"] == 3
    assert restored["definition"]["system_prompt"] != "New"

    clone = client.post(f"{url}/clone").json()
    assert clone["id"] != agent["id"] and clone["version"] == 1
    assert client.post("/api/agents", json={"name": "X", "template": "no"}).status_code == 409


def test_model_runtime_and_definition_are_separate_fields(client):
    names = {field["name"] for field in client.get("/api/agent-fields").json()}
    assert {
        "role", "system_prompt", "model", "runtime", "tools", "mcp_servers", "memory",
        "input_schema", "output_schema", "max_turns", "permissions", "max_retries", "session",
    } <= names  # fmt: skip


def test_every_runtime_declares_capabilities(client):
    runtimes = {item["id"]: item for item in client.get("/api/runtimes").json()}
    assert set(runtimes) == {"native", "claude-agent-sdk", "antigravity-sdk"}
    assert runtimes["native"]["capabilities"]["tools"] is False
    assert runtimes["claude-agent-sdk"]["capabilities"]["pause"] is False
    assert runtimes["claude-agent-sdk"]["paid"] is True
    assert runtimes["native"]["needs_secret"] is False


async def _call_all(adapter: RuntimeAdapter) -> list[str]:
    refused = []
    for name in ("pause", "resume", "cancel", "get_session", "restore_session"):
        try:
            await getattr(adapter, name)("s")
        except UnsupportedCapability as error:
            refused.append(error.capability)
    return refused


@pytest.mark.asyncio
async def test_unsupported_operations_are_refused_not_simulated():
    refused = await _call_all(ClaudeAgentRuntime())
    assert {"pause", "resume"} <= set(refused)


@pytest.mark.asyncio
async def test_native_refuses_tools_it_does_not_have():
    with pytest.raises(UnsupportedCapability):
        await NativeRuntime(None).execute(AgentRequest("p", "m", tools=["Read"]), None)


def test_claude_process_cannot_fall_back_to_a_subscription():
    options = build_options(AgentRequest("p", "sonnet"), "key", "/tmp/x")
    assert options["env"] == {"ANTHROPIC_API_KEY": "key", "CLAUDE_CODE_OAUTH_TOKEN": ""}
    assert options["setting_sources"] == []
    assert options["tools"] == []
    assert options["permission_mode"] == "default"


@pytest.mark.asyncio
async def test_claude_runtime_needs_a_key():
    with pytest.raises(Exception, match="needs an API key"):
        await ClaudeAgentRuntime().execute(AgentRequest("p", "sonnet", allow_paid=True), None)


def test_antigravity_stays_on_the_sdk_read_only_default():
    config = build_config(AgentRequest("p", "gemini", system_prompt="s"), "key", "/tmp/x")
    assert "capabilities" not in config
    assert config["api_key"] == "key"
    assert config["system_instructions"] == "s"


def test_sdk_option_names_match_the_installed_sdks():
    sdk = pytest.importorskip("claude_agent_sdk")
    sdk.ClaudeAgentOptions(**build_options(AgentRequest("p", "sonnet", max_turns=2), "k", "/tmp"))
    antigravity = pytest.importorskip("google.antigravity")
    antigravity.LocalAgentConfig(**build_config(AgentRequest("p", "m"), "k", "/tmp"))


def test_llm_agent_runs_a_local_model_and_records_what_answered(client, fake):
    reference = local_model(client, fake)
    node = n("a", "llm_agent", model=reference, system_prompt="Be brief")
    execution = agent_flow(client, node)
    detail = wait_for(client, execution["id"], "COMPLETED", timeout=20)
    assert detail["output"] == {"result": "ready"}
    usage = next(row for row in detail["nodes"] if row["node_id"] == "a")["usage"]
    assert usage["runtime"] == "native"
    assert usage["requested"] == reference
    assert "local-coder" in usage["model"]
    assert detail["metrics"]["output_tokens"] == 1
    roles = [m["role"] for m in fake.requests[0]["body"]["messages"]]
    assert roles == ["system", "user"]


def test_paid_models_need_permission_on_the_run(client, fake):
    reference = paid_model(client, fake)
    node = n("a", "llm_agent", model=reference)
    refused = agent_flow(client, node)
    detail = wait_for(client, refused["id"], "FAILED", timeout=20)
    assert "does not allow paid calls" in detail["error"]
    assert fake.requests == []

    nodes = [n("in", "input"), node, n("out", "output")]
    workflow_id = workflow(client, nodes, [e("in", "a"), e("a", "out")])
    allowed = start(client, workflow_id, "x", allow_paid=True)
    assert wait_for(client, allowed["id"], "COMPLETED", timeout=20)["output"] == {"result": "ready"}


def test_fallback_uses_the_next_model_and_says_so(client, fake):
    working = local_model(client, fake)
    provider = client.post(
        "/api/providers",
        json={
            "type": "ollama",
            "name": "Down",
            "endpoint": "http://127.0.0.1:1",
            "timeout_seconds": 1,
        },
    ).json()
    client.post(f"/api/providers/{provider['id']}/models", json={"model_id": "gone"})
    nodes = [
        n("in", "input"),
        n("f", "model_fallback", models=["Down/gone", working]),
        n("a", "llm_agent", model=working),
        n("out", "output"),
    ]
    edges = [e("in", "a"), e("f", "a", "model", "model"), e("a", "out")]
    execution = start(client, workflow(client, nodes, edges), "x")
    detail = wait_for(client, execution["id"], "COMPLETED", timeout=30)
    usage = next(row for row in detail["nodes"] if row["node_id"] == "a")["usage"]
    assert usage["fallbacks_used"] == 1
    assert usage["requested"] == working


def test_unknown_models_and_broken_agents_stop_a_run_at_the_start(client):
    nodes = [n("in", "input"), n("a", "llm_agent", model="Nope/none"), n("out", "output")]
    response = client.post(
        f"/api/workflows/{workflow(client, nodes, [e('in', 'a'), e('a', 'out')])}/executions",
        json={},
    )
    assert response.status_code == 422
    assert any("not in the registry" in i["message"] for i in response.json()["issues"])

    agent = client.post("/api/agents", json={"name": "Empty"}).json()
    nodes = [n("in", "input"), n("c", "custom_agent", agent_id=agent["id"]), n("out", "output")]
    response = client.post(
        f"/api/workflows/{workflow(client, nodes, [e('in', 'c'), e('c', 'out')])}/executions",
        json={},
    )
    assert response.status_code == 422
    assert "required" in response.json()["issues"][0]["message"]


def test_custom_agent_runs_through_its_runtime(client, fake):
    reference = local_model(client, fake)
    agent = client.post("/api/agents", json={"name": "Dev", "template": "developer"}).json()
    definition = {**agent["definition"], "model": reference}
    client.patch(f"/api/agents/{agent['id']}", json={"definition": definition})
    execution = agent_flow(client, n("c", "custom_agent", agent_id=agent["id"]))
    detail = wait_for(client, execution["id"], "COMPLETED", timeout=20)
    usage = next(row for row in detail["nodes"] if row["node_id"] == "c")["usage"]
    assert usage["agent"] == "Dev"
    assert usage["agent_version"] == 2


def test_cloud_runtime_without_a_key_is_refused_before_starting(client):
    agent = client.post("/api/agents", json={"name": "Cloud"}).json()
    definition = {"system_prompt": "x", "runtime": "claude-agent-sdk", "model": "sonnet"}
    client.patch(f"/api/agents/{agent['id']}", json={"definition": definition})
    nodes = [n("in", "input"), n("c", "custom_agent", agent_id=agent["id"]), n("out", "output")]
    workflow_id = workflow(client, nodes, [e("in", "c"), e("c", "out")])
    response = client.post(f"/api/workflows/{workflow_id}/executions", json={"allow_paid": True})
    assert response.status_code == 422
    assert "no API key" in response.json()["issues"][0]["message"]


@dataclass
class _Scripted(RuntimeAdapter):
    """A test double registered only inside this test."""

    id = "scripted"
    title = "Scripted"
    description = "test"
    paid = False
    needs_secret = False
    capabilities = RuntimeCapabilities()

    async def execute(self, request: AgentRequest, api_key: str | None) -> AgentResult:
        raise RuntimeError("runtime exploded")


def test_a_runtime_failure_fails_the_node_visibly(client):
    client.app.state.runtimes.register(_Scripted())
    agent = client.post("/api/agents", json={"name": "Boom"}).json()
    definition = {"system_prompt": "x", "runtime": "scripted", "model": "m"}
    client.app.state.agents.update(agent["id"], None, definition)
    node = n("c", "custom_agent", agent_id=agent["id"], runtime={"max_retries": 0})
    execution = agent_flow(client, node)
    detail = wait_for(client, execution["id"], "FAILED", timeout=20)
    assert detail["error_node"] == "c"
    assert "exploded" in detail["error"]


def test_runtime_config_stores_a_reference_only(client):
    client.put("/api/secrets/claude", json={"value": "sk-ant-secret"})
    response = client.patch("/api/runtimes/claude-agent-sdk", json={"secret_name": "claude"})
    assert response.status_code == 200
    assert response.json()["has_secret"] is True
    assert "sk-ant-secret" not in response.text
    assert client.patch("/api/runtimes/nope", json={}).status_code == 404


class _Leaky(RuntimeAdapter):
    id = "leaky"
    title = "Leaky"
    description = "test"
    paid = False

    async def execute(self, request: AgentRequest, api_key: str | None) -> AgentResult:
        raise ValueError(f"bad request with key {api_key}")


def test_keys_are_removed_from_any_runtime_error(client):
    client.app.state.runtimes.register(_Leaky())
    client.put("/api/secrets/leak", json={"value": "sk-leaky-value"})
    client.patch("/api/runtimes/leaky", json={"secret_name": "leak"})
    agent = client.post("/api/agents", json={"name": "Leak"}).json()
    definition = {"system_prompt": "x", "runtime": "leaky", "model": "m"}
    client.app.state.agents.update(agent["id"], None, definition)
    execution = agent_flow(client, n("c", "custom_agent", agent_id=agent["id"]))
    detail = wait_for(client, execution["id"], "FAILED", timeout=20)
    assert "[redacted]" in detail["error"]
    assert "sk-leaky-value" not in str(detail)
    log = client.get(f"/api/executions/{execution['id']}/log").text
    assert "sk-leaky-value" not in log
