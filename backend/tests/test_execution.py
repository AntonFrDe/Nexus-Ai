import json
import time
from pathlib import Path

import pytest
from conftest import authed
from fastapi.testclient import TestClient

from nexus.execution.handlers import BUILT_IN_HANDLERS
from nexus.execution.manager import preflight
from nexus.execution.states import (
    TERMINAL,
    TRANSITIONS,
    ExecutionStatus,
    InvalidTransition,
    check_transition,
)
from nexus.nodes.catalog import create_node_registry
from nexus.workflows.schemas import WorkflowGraph


def n(id_: str, type_: str, **config) -> dict:
    runtime = config.pop("runtime", {})
    return {
        "id": id_,
        "type": f"core.{type_}",
        "position": {"x": 0, "y": 0},
        "config": config,
        "runtime": runtime,
    }


def e(source: str, target: str, source_port="out", target_port="in") -> dict:
    return {
        "id": f"{source}.{source_port}-{target}.{target_port}",
        "source": source,
        "source_port": source_port,
        "target": target,
        "target_port": target_port,
    }


def wait_for(client: TestClient, execution_id: str, *statuses: str, timeout=5.0) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        detail = client.get(f"/api/executions/{execution_id}").json()
        if detail["status"] in statuses:
            return detail
        assert time.monotonic() < deadline, f"stuck in {detail['status']}: {detail['error']}"
        time.sleep(0.01)


def wait_for_node(client: TestClient, execution_id: str, node_id: str) -> None:
    deadline = time.monotonic() + 5
    while True:
        detail = client.get(f"/api/executions/{execution_id}").json()
        if status_of(detail).get(node_id) == "RUNNING":
            return
        assert time.monotonic() < deadline, f"{node_id} never started"
        time.sleep(0.005)


def workflow(client: TestClient, nodes: list[dict], edges: list[dict], name="Flow") -> str:
    created = client.post("/api/workflows", json={"name": name}).json()
    body = {"name": name, "nodes": nodes, "edges": edges}
    assert client.put(f"/api/workflows/{created['id']}", json=body).status_code == 200
    return created["id"]


def start(client: TestClient, workflow_id: str, value=None, **options) -> dict:
    response = client.post(
        f"/api/workflows/{workflow_id}/executions", json={"input": value, **options}
    )
    assert response.status_code == 202, response.text
    return response.json()


def run(client: TestClient, nodes, edges, value=None, *statuses) -> dict:
    execution = start(client, workflow(client, nodes, edges), value)
    return wait_for(client, execution["id"], *(statuses or ("COMPLETED", "FAILED")))


def status_of(detail: dict) -> dict[str, str]:
    return {row["node_id"]: row["status"] for row in detail["nodes"]}


def test_every_status_has_transitions_and_bad_ones_are_refused():
    assert set(TRANSITIONS) == set(ExecutionStatus)
    check_transition(ExecutionStatus.RUNNING, ExecutionStatus.PAUSED)
    with pytest.raises(InvalidTransition):
        check_transition(ExecutionStatus.COMPLETED, ExecutionStatus.PAUSED)
    with pytest.raises(InvalidTransition):
        check_transition(ExecutionStatus.PENDING, ExecutionStatus.COMPLETED)
    assert ExecutionStatus.COMPLETED in TERMINAL


def test_sequence_produces_real_outputs_and_records(client):
    detail = run(
        client,
        [
            n("in", "input"),
            n("t", "data_transform", template='{"doubled": "{{input.value}}", "tag": "x"}'),
            n("out", "output", name="answer"),
        ],
        [e("in", "t"), e("t", "out")],
        {"value": 21},
    )
    assert detail["status"] == "COMPLETED"
    assert detail["output"] == {"answer": {"doubled": 21, "tag": "x"}}
    assert status_of(detail) == {"in": "COMPLETED", "t": "COMPLETED", "out": "COMPLETED"}
    assert detail["started_at"] and detail["ended_at"]
    assert detail["metrics"]["nodes_run"] == 3


def test_conditional_branch_skips_the_other_side(client):
    nodes = [
        n("in", "input"),
        n("if", "if_else", expression="score > 0.5"),
        n("yes", "output", name="yes"),
        n("no", "output", name="no"),
    ]
    edges = [e("in", "if"), e("if", "yes", "true"), e("if", "no", "false")]
    detail = run(client, nodes, edges, {"score": 0.9})
    assert detail["output"] == {"yes": {"score": 0.9}}
    assert status_of(detail)["no"] == "SKIPPED"
    assert run(client, nodes, edges, {"score": 0.1})["output"] == {"no": {"score": 0.1}}


def test_switch_routes_by_value(client):
    nodes = [
        n("in", "input"),
        n("s", "switch", value="kind", case_1="a", case_2="b"),
        n("o1", "output", name="one"),
        n("o2", "output", name="two"),
        n("o3", "output", name="other"),
    ]
    edges = [
        e("in", "s"),
        e("s", "o1", "case_1"),
        e("s", "o2", "case_2"),
        e("s", "o3", "default"),
    ]
    assert list(run(client, nodes, edges, {"kind": "b"})["output"]) == ["two"]
    assert list(run(client, nodes, edges, {"kind": "z"})["output"]) == ["other"]


def test_parallel_branches_of_different_length_all_reach_the_merge(client):
    nodes = [
        n("in", "input"),
        n("p", "parallel"),
        n("slow1", "delay", seconds=0.03),
        n("slow2", "delay", seconds=0.03),
        n("fast", "logger"),
        n("m", "merge"),
        n("out", "output"),
    ]
    edges = [
        e("in", "p"),
        e("p", "slow1", "branches"),
        e("slow1", "slow2"),
        e("p", "fast", "branches"),
        e("slow2", "m"),
        e("fast", "m"),
        e("m", "out"),
    ]
    detail = run(client, nodes, edges, "x")
    assert detail["output"]["result"] == ["x", "x"]
    assert sum(row["node_id"] == "m" for row in detail["nodes"]) == 1


def test_count_loop_runs_its_body_and_finishes(client):
    nodes = [
        n("in", "input"),
        n("l", "loop", mode="count", count=3),
        n("b", "logger"),
        n("out", "output"),
    ]
    edges = [
        e("in", "l"),
        e("l", "b", "body"),
        e("b", "l", target_port="repeat"),
        e("l", "out", "done"),
    ]
    detail = run(client, nodes, edges, "x")
    assert detail["status"] == "COMPLETED"
    assert sum(row["node_id"] == "b" for row in detail["nodes"]) == 3


def test_for_each_collects_each_body_result(client):
    nodes = [
        n("in", "input"),
        n("l", "loop", mode="for_each"),
        n("t", "data_transform", template='{"seen": "{{input}}"}'),
        n("out", "output"),
    ]
    edges = [
        e("in", "l"),
        e("l", "t", "body"),
        e("t", "l", target_port="repeat"),
        e("l", "out", "done"),
    ]
    assert run(client, nodes, edges, [1, 2])["output"]["result"] == [{"seen": 1}, {"seen": 2}]


def test_while_loop_hits_its_hard_limit_visibly(client):
    nodes = [
        n("in", "input"),
        n("l", "loop", mode="while", condition="true", max_iterations=3),
        n("b", "logger"),
        n("out", "output"),
    ]
    edges = [
        e("in", "l"),
        e("l", "b", "body"),
        e("b", "l", target_port="repeat"),
        e("l", "out", "done"),
    ]
    detail = run(client, nodes, edges, 1)
    assert detail["status"] == "FAILED"
    assert detail["error_node"] == "l"
    assert "limit of 3" in detail["error"]


def test_shared_variables_flow_between_nodes(client):
    nodes = [
        n("in", "input"),
        n("w", "variable", name="saved", operation="write"),
        n("r", "variable", name="saved", operation="read"),
        n("out", "output"),
    ]
    edges = [e("in", "w"), e("w", "r"), e("r", "out")]
    assert run(client, nodes, edges, 5)["output"] == {"result": 5}


def test_failure_names_the_node_and_stops_downstream(client):
    nodes = [n("in", "input"), n("j", "json_parser"), n("out", "output")]
    detail = run(client, nodes, [e("in", "j"), e("j", "out")], "not json")
    assert detail["status"] == "FAILED"
    assert detail["error_node"] == "j"
    assert status_of(detail)["j"] == "FAILED"
    assert "out" not in status_of(detail) or status_of(detail)["out"] != "COMPLETED"


def test_retries_are_recorded_then_fail(client):
    nodes = [
        n("in", "input"),
        n("j", "json_parser", runtime={"max_retries": 2}),
        n("out", "output"),
    ]
    execution = start(client, workflow(client, nodes, [e("in", "j"), e("j", "out")]), "nope")
    wait_for(client, execution["id"], "FAILED")
    log = client.get(f"/api/executions/{execution['id']}/log").json()
    assert [item["type"] for item in log].count("node_retrying") == 2


def test_timeout_fails_the_node(client):
    nodes = [
        n("in", "input"),
        n("d", "delay", seconds=5, runtime={"timeout_seconds": 0.02}),
        n("out", "output"),
    ]
    detail = run(client, nodes, [e("in", "d"), e("d", "out")], 1)
    assert detail["status"] == "FAILED"
    assert "Timed out" in detail["error"]


def test_error_handler_catches_nodes_set_to_continue(client):
    nodes = [
        n("in", "input"),
        n("j", "json_parser", runtime={"on_error": "continue"}),
        n("ok", "output", name="parsed"),
        n("h", "error_handler"),
        n("err", "output", name="failure"),
    ]
    edges = [e("in", "j"), e("j", "ok"), e("h", "err", "error")]
    detail = run(client, nodes, edges, "bad")
    assert detail["status"] == "COMPLETED"
    assert detail["output"]["failure"]["node_id"] == "j"
    assert "parsed" not in detail["output"]


def test_stop_ends_the_run_with_its_status(client):
    nodes = [n("in", "input"), n("s", "stop", status="failed")]
    detail = run(client, nodes, [e("in", "s")], 1)
    assert detail["status"] == "FAILED"
    assert "Stop node" in detail["error"]


APPROVAL_NODES = [
    n("in", "input"),
    n("a", "human_approval", prompt="Publish?"),
    n("yes", "output", name="yes"),
    n("no", "output", name="no"),
]
APPROVAL_EDGES = [e("in", "a"), e("a", "yes", "approved"), e("a", "no", "rejected")]


@pytest.mark.parametrize(("decision", "output"), [("approved", "yes"), ("rejected", "no")])
def test_human_approval_waits_then_follows_the_decision(client, decision, output):
    execution = start(client, workflow(client, APPROVAL_NODES, APPROVAL_EDGES), "doc")
    detail = wait_for(client, execution["id"], "WAITING_FOR_APPROVAL")
    assert detail["pending_approvals"][0]["prompt"] == "Publish?"
    assert status_of(detail)["a"] == "WAITING"
    url = f"/api/executions/{execution['id']}/approval"
    assert client.post(url, json={"decision": decision}).status_code == 202
    assert list(wait_for(client, execution["id"], "COMPLETED")["output"]) == [output]
    assert client.post(url, json={"decision": decision}).status_code == 409


def test_approval_survives_a_restart(settings):
    with authed(settings) as first:
        execution = start(first, workflow(first, APPROVAL_NODES, APPROVAL_EDGES), "doc")
        wait_for(first, execution["id"], "WAITING_FOR_APPROVAL")
    with authed(settings) as second:
        url = f"/api/executions/{execution['id']}"
        assert second.get(url).json()["status"] == "WAITING_FOR_APPROVAL"
        second.post(f"{url}/approval", json={"decision": "approved"})
        assert wait_for(second, execution["id"], "COMPLETED")["output"] == {"yes": "doc"}


def chain(*steps: dict) -> tuple[list[dict], list[dict]]:
    ids = [step["id"] for step in steps]
    return list(steps), [e(a, b) for a, b in zip(ids, ids[1:], strict=False)]


def test_pause_stops_between_nodes_and_resume_finishes(client):
    nodes, edges = chain(
        n("in", "input"), n("d", "delay", seconds=0.15), n("l", "logger"), n("out", "output")
    )
    execution = start(client, workflow(client, nodes, edges), "x")
    url = f"/api/executions/{execution['id']}"
    wait_for_node(client, execution["id"], "d")
    assert client.post(f"{url}/pause").status_code == 202
    detail = wait_for(client, execution["id"], "PAUSED")
    assert status_of(detail)["d"] == "COMPLETED", "the running node finishes"
    assert status_of(detail).get("out") != "COMPLETED"
    assert client.post(f"{url}/resume").status_code == 202
    assert wait_for(client, execution["id"], "COMPLETED")["output"] == {"result": "x"}


def test_a_pause_never_answers_a_later_approval(client):
    """Interrupts resume by position: a released pause must not satisfy the approval after it."""
    nodes = [
        n("in", "input"),
        n("d", "delay", seconds=0.1),
        n("a", "human_approval", prompt="Sure?"),
        n("yes", "output", name="yes"),
        n("no", "output", name="no"),
    ]
    edges = [e("in", "d"), e("d", "a"), e("a", "yes", "approved"), e("a", "no", "rejected")]
    execution = start(client, workflow(client, nodes, edges), "x")
    url = f"/api/executions/{execution['id']}"
    wait_for_node(client, execution["id"], "d")
    client.post(f"{url}/pause")
    wait_for(client, execution["id"], "PAUSED")
    client.post(f"{url}/resume")
    wait_for(client, execution["id"], "WAITING_FOR_APPROVAL")
    client.post(f"{url}/approval", json={"decision": "rejected"})
    assert list(wait_for(client, execution["id"], "COMPLETED")["output"]) == ["no"]


def test_cancel_stops_a_running_node(client):
    nodes, edges = chain(n("in", "input"), n("d", "delay", seconds=30), n("out", "output"))
    execution = start(client, workflow(client, nodes, edges), 1)
    url = f"/api/executions/{execution['id']}"
    wait_for_node(client, execution["id"], "d")
    assert client.post(f"{url}/cancel").status_code == 202
    detail = wait_for(client, execution["id"], "CANCELLED")
    assert status_of(detail)["d"] == "FAILED"
    assert client.post(f"{url}/cancel").status_code == 409


def test_a_long_run_does_not_block_the_api(client):
    nodes, edges = chain(n("in", "input"), n("d", "delay", seconds=30), n("out", "output"))
    execution = start(client, workflow(client, nodes, edges), 1)
    started = time.monotonic()
    assert client.get("/api/workspaces").status_code == 200
    assert time.monotonic() - started < 1
    client.post(f"/api/executions/{execution['id']}/cancel")
    wait_for(client, execution["id"], "CANCELLED")


def test_restart_during_a_run_leaves_it_resumable(settings):
    with authed(settings) as first:
        nodes, edges = chain(n("in", "input"), n("d", "delay", seconds=0.3), n("out", "output"))
        execution = start(first, workflow(first, nodes, edges), "kept")
        wait_for(first, execution["id"], "RUNNING")
        time.sleep(0.05)
    with authed(settings) as second:
        url = f"/api/executions/{execution['id']}"
        detail = second.get(url).json()
        assert detail["status"] == "PAUSED"
        assert "resume" in detail["error"]
        assert second.post(f"{url}/resume").status_code == 202
        assert wait_for(second, execution["id"], "COMPLETED")["output"] == {"result": "kept"}


def test_a_failed_run_resumes_from_its_checkpoint(client):
    """The failed node runs again; nodes that completed do not."""
    nodes, edges = chain(n("in", "input"), n("l", "logger"), n("j", "json_parser"))
    execution = start(client, workflow(client, nodes, edges), "bad")
    wait_for(client, execution["id"], "FAILED")
    url = f"/api/executions/{execution['id']}"
    assert client.post(f"{url}/resume").status_code == 202
    detail = wait_for(client, execution["id"], "FAILED")
    assert sum(row["node_id"] == "l" for row in detail["nodes"]) == 1
    assert sum(row["node_id"] == "j" for row in detail["nodes"]) == 2


def test_retry_is_a_new_run_of_the_original_definition(client):
    nodes, edges = chain(n("in", "input"), n("out", "output"))
    workflow_id = workflow(client, nodes, edges)
    first = start(client, workflow_id, "v1")
    wait_for(client, first["id"], "COMPLETED")
    client.put(f"/api/workflows/{workflow_id}", json={"name": "Changed", "nodes": [], "edges": []})
    second = client.post(f"/api/executions/{first['id']}/retry").json()
    assert second["id"] != first["id"]
    assert wait_for(client, second["id"], "COMPLETED")["output"] == {"result": "v1"}


def test_checkpoint_restoration_reruns_later_nodes(client):
    nodes, edges = chain(n("in", "input"), n("l", "logger"), n("out", "output"))
    execution = start(client, workflow(client, nodes, edges), "x")
    wait_for(client, execution["id"], "COMPLETED")
    url = f"/api/executions/{execution['id']}"
    history = client.get(f"{url}/checkpoints").json()
    target = next(item for item in history if item["next"] == ["l"])
    assert client.post(f"{url}/restore", json={"checkpoint_id": "nope"}).status_code == 409
    assert (
        client.post(f"{url}/restore", json={"checkpoint_id": target["checkpoint_id"]}).status_code
        == 202
    )
    detail = wait_for(client, execution["id"], "COMPLETED")
    assert sum(row["node_id"] == "l" for row in detail["nodes"]) == 2


def test_single_node_and_from_node_modes(client):
    nodes, edges = chain(
        n("in", "input"), n("t", "data_transform", template='"{{input}}!"'), n("out", "output")
    )
    workflow_id = workflow(client, nodes, edges)
    single = start(client, workflow_id, "hi", mode="node", node_id="t")
    detail = wait_for(client, single["id"], "COMPLETED")
    assert status_of(detail) == {"t": "COMPLETED"}
    assert detail["nodes"][0]["output"] == "hi!"

    partial = start(client, workflow_id, "hey", mode="from_node", node_id="t")
    detail = wait_for(client, partial["id"], "COMPLETED")
    assert detail["output"] == {"result": "hey!"}
    assert "in" not in status_of(detail)


def test_invalid_and_unimplemented_workflows_never_start(client):
    invalid = workflow(client, [n("d", "delay")], [])
    response = client.post(f"/api/workflows/{invalid}/executions", json={})
    assert response.status_code == 422
    assert {issue["code"] for issue in response.json()["issues"]} >= {"invalid_config"}

    agent = workflow(
        client,
        [n("in", "input"), n("a", "coding_agent", model="x", workspace_path="/tmp")],
        [e("in", "a")],
    )
    response = client.post(f"/api/workflows/{agent}/executions", json={})
    assert response.status_code == 422
    issue = next(i for i in response.json()["issues"] if i["code"] == "not_executable")
    assert "cannot run yet" in issue["message"]
    assert client.get("/api/executions").json() == []


def test_side_effect_nodes_have_no_handler_yet():
    """Terminal, Python and file nodes must stay unrunnable until permissions are enforced."""
    assert not {
        "core.terminal",
        "core.python_executor",
        "core.file_reader",
        "core.file_writer",
        "core.http_request",
        "core.browser",
        "core.database",
    } & set(BUILT_IN_HANDLERS)
    graph = WorkflowGraph.model_validate({"nodes": [n("t", "terminal", command="rm -rf /")]})
    codes = {i.code for i in preflight(graph, create_node_registry(), BUILT_IN_HANDLERS)}
    assert "not_executable" in codes


def test_sub_workflow_runs_as_a_single_step(client):
    child_nodes, child_edges = chain(
        n("in", "input"), n("t", "data_transform", template='"child {{input}}"'), n("out", "output")
    )
    child = workflow(client, child_nodes, child_edges, "Child")
    nodes, edges = chain(
        n("in", "input"), n("s", "sub_workflow", workflow_id=child), n("out", "output")
    )
    assert run(client, nodes, edges, "a")["output"] == {"result": "child a"}


def test_recursive_sub_workflow_fails_at_the_depth_limit(client):
    created = client.post("/api/workflows", json={"name": "Self"}).json()
    nodes, edges = chain(
        n("in", "input"),
        n("s", "sub_workflow", workflow_id=created["id"]),
        n("out", "output"),
    )
    client.put(
        f"/api/workflows/{created['id']}", json={"name": "Self", "nodes": nodes, "edges": edges}
    )
    execution = start(client, created["id"], 1)
    detail = wait_for(client, execution["id"], "FAILED", timeout=10)
    assert "nested" in detail["error"]


def test_events_stream_in_order_and_replay_from_a_position(client):
    nodes, edges = chain(n("in", "input"), n("out", "output"))
    execution = start(client, workflow(client, nodes, edges), 1)
    wait_for(client, execution["id"], "COMPLETED")
    url = f"/api/executions/{execution['id']}/events"
    with client.stream("GET", url) as stream:
        assert stream.headers["content-type"].startswith("text/event-stream")
        body = "".join(stream.iter_text())
    assert "event: end" in body
    assert body.index('"node_started"') < body.index('"node_completed"')
    ids = [int(line[4:]) for line in body.splitlines() if line.startswith("id: ")]
    assert ids == sorted(ids) and len(ids) > 3
    with client.stream("GET", f"{url}?after={ids[-1]}") as stream:
        assert "id:" not in "".join(stream.iter_text())


def test_runs_keep_their_definition_when_the_workflow_is_deleted(client):
    nodes, edges = chain(n("in", "input"), n("out", "output"))
    workflow_id = workflow(client, nodes, edges)
    execution = start(client, workflow_id, 1)
    wait_for(client, execution["id"], "COMPLETED")
    client.delete(f"/api/workflows/{workflow_id}")
    detail = client.get(f"/api/executions/{execution['id']}").json()
    assert detail["workflow_id"] is None
    assert detail["workflow_name"] == "Flow"


def test_list_filters_by_workflow(client):
    nodes, edges = chain(n("in", "input"), n("out", "output"))
    one, two = workflow(client, nodes, edges), workflow(client, nodes, edges)
    wait_for(client, start(client, one, 1)["id"], "COMPLETED")
    wait_for(client, start(client, two, 1)["id"], "COMPLETED")
    assert len(client.get("/api/executions").json()) == 2
    assert len(client.get(f"/api/executions?workflow_id={one}").json()) == 1


def test_invalid_expressions_are_reported_at_validation(client):
    graph = {"nodes": [n("i", "if_else", expression="__import__('os')")]}
    report = client.post("/api/workflows/validate", json=graph).json()
    assert "invalid_expression" in {issue["code"] for issue in report["issues"]}


def test_example_with_an_agent_is_refused_until_agents_exist(client):
    example = Path(__file__).parents[1] / "examples" / "research-summary.nexus.json"
    imported = client.post("/api/workflows/import", json=json.loads(example.read_text())).json()
    response = client.post(f"/api/workflows/{imported['id']}/executions", json={})
    assert response.status_code == 422


def test_runnable_example_works(client):
    example = Path(__file__).parents[1] / "examples" / "triage-with-approval.nexus.json"
    imported = client.post("/api/workflows/import", json=json.loads(example.read_text())).json()
    low = start(client, imported["id"], {"score": 0.1})
    assert list(wait_for(client, low["id"], "COMPLETED")["output"]) == ["low_score"]
    high = start(client, imported["id"], {"score": 0.9})
    wait_for(client, high["id"], "WAITING_FOR_APPROVAL")
    client.post(f"/api/executions/{high['id']}/approval", json={"decision": "approved"})
    assert list(wait_for(client, high["id"], "COMPLETED")["output"]) == ["accepted"]
