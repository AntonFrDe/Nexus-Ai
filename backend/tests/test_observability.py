import json
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fake_provider import API_KEY, start_fake_provider
from test_agents import paid_model
from test_execution import e, n, start, wait_for, workflow

from nexus.observability.langfuse import build_trace as build_otlp
from nexus.providers.adapter import Completion
from nexus.providers.service import ProviderRegistry


@pytest.fixture
def fake():
    server = start_fake_provider()
    yield server
    server.shutdown()


def chain(*steps: dict) -> tuple[list[dict], list[dict]]:
    ids = [step["id"] for step in steps]
    return list(steps), [e(a, b) for a, b in zip(ids, ids[1:], strict=False)]


def transform(template: str) -> dict:
    return n("t", "data_transform", template=template)


def run_chain(client, *steps, value="x", **options) -> dict:
    nodes, edges = chain(*steps)
    return start(client, workflow(client, nodes, edges), value, **options)


def test_trace_names_the_failed_node_why_and_on_what_input(client):
    execution = run_chain(
        client,
        n("in", "input"),
        {**n("parse", "json_parser"), "label": "Parse reply"},
        n("out", "output"),
        value="not json",
    )
    wait_for(client, execution["id"], "FAILED")
    trace = client.get(f"/api/executions/{execution['id']}/trace").json()
    assert trace["failure"]["node_id"] == "parse"
    assert trace["failure"]["label"] == "Parse reply"
    assert "Expecting value" in trace["failure"]["message"]
    assert trace["failure"]["input"] == "not json"
    assert trace["recorded"] is True
    spans = {span["node_id"]: span for span in trace["spans"]}
    assert spans["parse"]["status"] == "FAILED"
    assert spans["in"]["duration_ms"] is not None


def test_a_successful_trace_has_no_failure(client):
    execution = run_chain(client, n("in", "input"), n("out", "output"))
    wait_for(client, execution["id"], "COMPLETED")
    assert client.get(f"/api/executions/{execution['id']}/trace").json()["failure"] is None


def test_variables_can_be_inspected_between_nodes(client):
    execution = run_chain(
        client,
        n("in", "input"),
        n("w", "variable", name="kept", operation="write"),
        n("out", "output"),
        value=7,
    )
    wait_for(client, execution["id"], "COMPLETED")
    url = f"/api/executions/{execution['id']}/checkpoints"
    history = client.get(url).json()
    before = next(item for item in history if item["next"] == ["w"])
    after = next(item for item in history if item["next"] == ["out"])
    assert client.get(f"{url}/{before['checkpoint_id']}").json()["variables"] == {}
    state = client.get(f"{url}/{after['checkpoint_id']}").json()
    assert state["variables"] == {"kept": 7}
    assert state["outputs"]["in"] == 7
    assert client.get(f"{url}/nope").status_code == 409


def test_step_mode_stops_before_each_node(client):
    execution = run_chain(client, n("in", "input"), n("l", "logger"), n("out", "output"), step=True)
    url = f"/api/executions/{execution['id']}"
    done = []
    for _ in range(3):
        detail = wait_for(client, execution["id"], "PAUSED")
        done.append(sorted(r["node_id"] for r in detail["nodes"] if r["status"] == "COMPLETED"))
        assert client.post(f"{url}/resume").status_code == 202
        wait_for(client, execution["id"], "PAUSED", "COMPLETED")
    assert done == [[], ["in"], ["in", "l"]]
    assert wait_for(client, execution["id"], "COMPLETED")["output"] == {"result": "x"}


def test_step_mode_can_run_to_the_end(client):
    execution = run_chain(client, n("in", "input"), n("l", "logger"), n("out", "output"), step=True)
    url = f"/api/executions/{execution['id']}"
    wait_for(client, execution["id"], "PAUSED")
    assert client.post(f"{url}/resume", json={"run_to_end": True}).status_code == 202
    assert wait_for(client, execution["id"], "COMPLETED")["step_mode"] is False


def test_step_mode_reaches_a_human_approval_correctly(client):
    nodes = [
        n("in", "input"),
        n("a", "human_approval", prompt="Sure?"),
        n("yes", "output", name="yes"),
        n("no", "output", name="no"),
    ]
    edges = [e("in", "a"), e("a", "yes", "approved"), e("a", "no", "rejected")]
    execution = start(client, workflow(client, nodes, edges), "x", step=True)
    url = f"/api/executions/{execution['id']}"
    wait_for(client, execution["id"], "PAUSED")
    client.post(f"{url}/resume")
    wait_for(client, execution["id"], "PAUSED")
    client.post(f"{url}/resume")
    wait_for(client, execution["id"], "WAITING_FOR_APPROVAL")
    client.post(f"{url}/approval", json={"decision": "rejected"})
    for _ in range(3):
        status = wait_for(client, execution["id"], "PAUSED", "COMPLETED")["status"]
        if status == "COMPLETED":
            break
        client.post(f"{url}/resume", json={"run_to_end": True})
    assert list(wait_for(client, execution["id"], "COMPLETED")["output"]) == ["no"]


def test_replay_changes_only_what_was_asked_and_keeps_the_original(client):
    execution = run_chain(
        client, n("in", "input"), transform('"one {{input}}"'), n("out", "output")
    )
    wait_for(client, execution["id"], "COMPLETED")
    url = f"/api/executions/{execution['id']}"
    before = client.get(url).json()

    response = client.post(
        f"{url}/replay", json={"overrides": {"t": {"template": '"two {{input}}"'}}}
    )
    assert response.status_code == 202
    replay = wait_for(client, response.json()["id"], "COMPLETED")
    assert replay["output"] == {"result": "two x"}
    assert replay["replay_of"] == execution["id"]
    assert replay["overrides"] == {"t": {"template": '"two {{input}}"'}}
    assert client.get(url).json() == before


def test_replay_refuses_unknown_nodes_and_invalid_changes(client):
    execution = run_chain(client, n("in", "input"), n("d", "delay", seconds=0), n("out", "output"))
    wait_for(client, execution["id"], "COMPLETED")
    url = f"/api/executions/{execution['id']}/replay"
    assert client.post(url, json={"overrides": {"nope": {}}}).status_code == 409
    assert client.post(url, json={"overrides": {"d": {"seconds": -1}}}).status_code == 422


def test_replay_does_not_inherit_permission_to_spend(client, fake):
    reference = paid_model(client, fake)
    nodes, edges = chain(n("in", "input"), n("a", "llm_agent", model=reference), n("out", "output"))
    workflow_id = workflow(client, nodes, edges)
    execution = start(client, workflow_id, "x", allow_paid=True)
    wait_for(client, execution["id"], "COMPLETED", timeout=20)
    url = f"/api/executions/{execution['id']}/replay"
    assert client.post(url, json={}).status_code == 422
    assert client.post(url, json={"allow_paid": True}).status_code == 202


def test_comparison_shows_what_changed(client):
    execution = run_chain(client, n("in", "input"), transform('"one"'), n("out", "output"))
    wait_for(client, execution["id"], "COMPLETED")
    replay = client.post(
        f"/api/executions/{execution['id']}/replay",
        json={"overrides": {"t": {"template": '"two"'}}},
    ).json()
    wait_for(client, replay["id"], "COMPLETED")
    report = client.get(
        "/api/executions/compare", params={"left": execution["id"], "right": replay["id"]}
    ).json()
    rows = {row["node_id"]: row for row in report["rows"]}
    assert rows["in"]["same_output"] and not rows["in"]["config_changed"]
    assert rows["t"]["config_changed"] and not rows["t"]["same_output"]
    assert rows["t"]["left"]["output"] == "one"
    assert rows["t"]["right"]["output"] == "two"


def test_comparison_handles_nodes_only_one_run_reached(client):
    nodes = [
        n("in", "input"),
        n("if", "if_else", expression="input > 1"),
        n("a", "logger"),
        n("b", "logger"),
    ]
    edges = [e("in", "if"), e("if", "a", "true"), e("if", "b", "false")]
    workflow_id = workflow(client, nodes, edges)
    one = start(client, workflow_id, 5)
    two = start(client, workflow_id, 0)
    wait_for(client, one["id"], "COMPLETED")
    wait_for(client, two["id"], "COMPLETED")
    report = client.get(
        "/api/executions/compare", params={"left": one["id"], "right": two["id"]}
    ).json()
    rows = {row["node_id"]: row for row in report["rows"]}
    assert rows["a"]["same_status"] is False


def test_cost_comes_from_registered_prices():
    answer = Completion("x", "m", 1_000_000, 500_000, 1)
    assert ProviderRegistry._cost(answer, (2.0, 8.0), False) == 6.0
    assert ProviderRegistry._cost(answer, (None, 8.0), False) is None
    assert ProviderRegistry._cost(answer, (2.0, 8.0), True) == 0.0


def test_analytics_counts_runs_tokens_and_cost(client, fake):
    reference = paid_model(client, fake)
    model = client.get("/api/models").json()[0]
    client.patch(
        f"/api/models/{model['id']}",
        json={"input_cost_per_mtok": 1_000_000, "output_cost_per_mtok": 2_000_000},
    )
    nodes, edges = chain(n("in", "input"), n("a", "llm_agent", model=reference), n("out", "output"))
    execution = start(client, workflow(client, nodes, edges), "x", allow_paid=True)
    wait_for(client, execution["id"], "COMPLETED", timeout=20)
    failed = run_chain(client, n("in", "input"), n("j", "json_parser"), value="bad")
    wait_for(client, failed["id"], "FAILED")

    report = client.get("/api/analytics?days=7").json()
    assert report["runs"] == 2
    assert report["statuses"] == {"COMPLETED": 1, "FAILED": 1}
    assert report["totals"]["cost_usd"] == pytest.approx(6.0)
    assert report["totals"]["unpriced"] == 0
    assert report["by_model"][0]["calls"] == 1
    assert report["by_workflow"][0]["workflow"] == "Flow"
    assert len(report["by_day"]) == 1
    assert report["top_errors"][0]["count"] == 1


def test_unknown_prices_are_reported_not_counted_as_free(client, fake):
    reference = paid_model(client, fake)
    nodes, edges = chain(n("in", "input"), n("a", "llm_agent", model=reference), n("out", "output"))
    execution = start(client, workflow(client, nodes, edges), "x", allow_paid=True)
    wait_for(client, execution["id"], "COMPLETED", timeout=20)
    assert client.get("/api/analytics").json()["totals"]["unpriced"] == 1


def test_structured_log_holds_status_but_never_content(client, settings):
    execution = run_chain(client, n("in", "input"), n("out", "output"), value="private text")
    wait_for(client, execution["id"], "COMPLETED")
    lines = (settings.data_dir / "logs" / "nexus.log").read_text().splitlines()
    entries = [json.loads(line) for line in lines]
    assert any(
        entry["event"] == "execution_status" and entry["status"] == "COMPLETED" for entry in entries
    )
    assert "private text" not in "".join(lines)


class _Langfuse(BaseHTTPRequestHandler):
    def log_message(self, *_args) -> None:
        pass

    def _reply(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    def do_GET(self) -> None:
        self.server.seen.append((self.path, dict(self.headers), None))
        self._reply(self.server.status)

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.seen.append((self.path, dict(self.headers), body))
        self._reply(self.server.status)


@pytest.fixture
def langfuse():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Langfuse)
    server.seen = []
    server.status = 200
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server
    server.shutdown()


def configure(client, server, **options) -> None:
    client.put("/api/secrets/lf", json={"value": API_KEY})
    body = {
        "enabled": True,
        "host": f"http://127.0.0.1:{server.server_address[1]}",
        "public_key": "pk-lf-test",
        "secret_name": "lf",
        **options,
    }
    assert client.put("/api/observability/langfuse", json=body).status_code == 200


def wait_for_export(server) -> tuple:
    deadline = time.monotonic() + 5
    while not server.seen:
        assert time.monotonic() < deadline
        time.sleep(0.01)
    return server.seen[0]


def test_langfuse_is_off_by_default_and_sends_nothing(client):
    assert client.get("/api/observability/langfuse").json()["enabled"] is False
    execution = run_chain(client, n("in", "input"), n("out", "output"))
    wait_for(client, execution["id"], "COMPLETED")
    log = client.get(f"/api/executions/{execution['id']}/log").json()
    assert "export_failed" not in [item["type"] for item in log]


def test_langfuse_export_uses_otlp_and_omits_content_by_default(client, langfuse):
    configure(client, langfuse)
    execution = run_chain(client, n("in", "input"), n("out", "output"), value="private text")
    wait_for(client, execution["id"], "COMPLETED")
    path, headers, body = wait_for_export(langfuse)
    assert path == "/api/public/otel/v1/traces"
    assert headers["Authorization"].startswith("Basic ")
    assert headers["x-langfuse-ingestion-version"] == "4"
    spans = body["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert len(spans) == 3
    assert spans[1]["parentSpanId"] == spans[0]["spanId"]
    assert len(spans[0]["traceId"]) == 32 and len(spans[0]["spanId"]) == 16
    assert "private text" not in json.dumps(body)


def test_langfuse_content_is_sent_only_when_chosen(client, langfuse):
    configure(client, langfuse, include_content=True)
    execution = run_chain(client, n("in", "input"), n("out", "output"), value="shared text")
    wait_for(client, execution["id"], "COMPLETED")
    assert "shared text" in json.dumps(wait_for_export(langfuse)[2])


def test_a_failed_export_never_changes_the_run(client, langfuse):
    langfuse.status = 500
    configure(client, langfuse)
    execution = run_chain(client, n("in", "input"), n("out", "output"))
    assert wait_for(client, execution["id"], "COMPLETED")["status"] == "COMPLETED"
    deadline = time.monotonic() + 5
    while True:
        log = client.get(f"/api/executions/{execution['id']}/log").json()
        if any(item["type"] == "export_failed" for item in log):
            break
        assert time.monotonic() < deadline
    assert API_KEY not in str(log)


def test_langfuse_check_reports_the_outcome(client, langfuse):
    configure(client, langfuse)
    assert client.post("/api/observability/langfuse/check").json()["ok"] is True
    assert langfuse.seen[0][0] == "/api/public/projects"
    langfuse.status = 401
    result = client.post("/api/observability/langfuse/check").json()
    assert result["ok"] is False and "401" in result["message"]


def test_otlp_document_is_valid_for_a_run_with_no_nodes():
    class Run:
        id = "x"
        workflow_name = "Flow"
        status = "FAILED"
        started_at = None
        created_at = datetime(2026, 1, 1)
        ended_at = None

    document = build_otlp(Run, [], False)
    assert document["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["status"]["code"] == 2
