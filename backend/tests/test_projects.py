import json

import pytest
from conftest import authed
from fake_provider import start_fake_provider
from test_agents import local_model, paid_model

from nexus.projects.proposals import split_proposal

PROPOSAL = {
    "roadmap": {"title": "Notes app", "steps": [{"title": "Scope", "detail": "Define the MVP"}]},
    "agents": [{"name": "Planner", "role": "Plan", "system_prompt": "You plan."}],
}
REPLY = f"Voici ma proposition.\n\n```nexus-proposal\n{json.dumps(PROPOSAL)}\n```"


@pytest.fixture
def fake():
    server = start_fake_provider()
    yield server
    server.shutdown()


def project(client, name="Notes") -> str:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def say(client, project_id: str, content: str, model: str, **options) -> str:
    with client.stream(
        "POST",
        f"/api/projects/{project_id}/chat",
        json={"content": content, "model": model, **options},
    ) as response:
        assert response.status_code == 200
        return "".join(response.iter_text())


def test_split_finds_a_valid_proposal_and_hides_the_block():
    text, proposal = split_proposal(REPLY)
    assert text == "Voici ma proposition."
    assert proposal.roadmap.title == "Notes app"


@pytest.mark.parametrize(
    "reply",
    [
        "Just text",
        "```nexus-proposal\nnot json\n```",
        '```nexus-proposal\n{"roadmap": {"title": "x", "steps": []}}\n```',
        '```nexus-proposal\n{"agents": [{"name": "x"}]}\n```',
        '```nexus-proposal\n{"run_shell": "rm -rf /"}\n```',
        "```nexus-proposal\n{}\n```",
    ],
)
def test_anything_unexpected_is_not_a_proposal(reply):
    text, proposal = split_proposal(reply)
    assert proposal is None
    assert text == reply.strip()


def test_too_many_agents_is_not_a_proposal():
    agents = [{"name": str(i), "system_prompt": "x"} for i in range(11)]
    block = json.dumps({"agents": agents})
    assert split_proposal(f"```nexus-proposal\n{block}\n```")[1] is None


def test_project_lifecycle_and_list_order(client):
    first = project(client, "One")
    second = project(client, "Two")
    assert [item["name"] for item in client.get("/api/projects").json()] == ["Two", "One"]
    client.patch(f"/api/projects/{first}", json={"name": "Renamed"})
    assert client.get("/api/projects").json()[0]["name"] == "Renamed"
    assert client.delete(f"/api/projects/{second}").status_code == 204
    assert client.get(f"/api/projects/{second}").status_code == 404
    assert client.post("/api/projects", json={"name": ""}).status_code == 422


def test_chat_streams_and_is_saved_with_its_model(client, fake):
    model = local_model(client, fake)
    project_id = project(client)
    body = say(client, project_id, "Bonjour", model)
    assert "event: delta" in body and "event: done" in body
    messages = client.get(f"/api/projects/{project_id}").json()["messages"]
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert messages[1]["content"] == "ready"
    assert messages[1]["model"] == model
    summary = client.get("/api/projects").json()[0]
    assert summary["messages"] == 2


def test_the_conversation_history_reaches_the_model(client, fake):
    model = local_model(client, fake)
    project_id = project(client)
    say(client, project_id, "Premier", model)
    say(client, project_id, "Second", model)
    sent = fake.requests[-1]["body"]["messages"]
    assert sent[0]["role"] == "system"
    assert [item["content"] for item in sent[1:]] == ["Premier", "ready", "Second"]


def test_a_proposal_creates_nothing_until_approved(client, fake):
    fake.reply = REPLY
    model = local_model(client, fake)
    project_id = project(client)
    say(client, project_id, "Fais une roadmap", model)
    detail = client.get(f"/api/projects/{project_id}").json()
    message = detail["messages"][1]
    assert message["content"] == "Voici ma proposition."
    assert message["proposal_status"] == "pending"
    assert detail["results"] == []
    assert client.get("/api/agents").json() == []

    url = f"/api/projects/{project_id}/messages/{message['id']}"
    approved = client.post(f"{url}/approve").json()
    kinds = sorted(item["kind"] for item in approved["results"])
    assert kinds == ["agent", "roadmap"]
    agents = client.get("/api/agents").json()
    assert agents[0]["name"] == "Planner"
    assert agents[0]["definition"]["model"] == model
    assert client.post(f"{url}/approve").status_code == 409
    assert len(client.get("/api/agents").json()) == 1


def test_a_rejected_proposal_creates_nothing(client, fake):
    fake.reply = REPLY
    model = local_model(client, fake)
    project_id = project(client)
    say(client, project_id, "Fais une roadmap", model)
    message = client.get(f"/api/projects/{project_id}").json()["messages"][1]
    url = f"/api/projects/{project_id}/messages/{message['id']}"
    assert client.post(f"{url}/reject").json()["results"] == []
    assert client.post(f"{url}/approve").status_code == 409
    assert client.get("/api/agents").json() == []


def test_approval_is_tied_to_its_own_project(client, fake):
    fake.reply = REPLY
    model = local_model(client, fake)
    owner = project(client, "Owner")
    other = project(client, "Other")
    say(client, owner, "Roadmap", model)
    message = client.get(f"/api/projects/{owner}").json()["messages"][1]
    url = f"/api/projects/{other}/messages/{message['id']}/approve"
    assert client.post(url).status_code == 404


def test_unknown_models_are_refused_and_nothing_is_saved(client):
    project_id = project(client)
    response = client.post(
        f"/api/projects/{project_id}/chat", json={"content": "x", "model": "Nope/none"}
    )
    assert response.status_code == 409
    assert client.get(f"/api/projects/{project_id}").json()["messages"] == []


def test_paid_models_need_confirmation(client, fake):
    model = paid_model(client, fake)
    project_id = project(client)
    assert "event: failure" in say(client, project_id, "x", model)
    assert fake.requests == []


def test_conversations_survive_a_restart(settings, fake):
    with authed(settings) as first:
        model = local_model(first, fake)
        project_id = project(first)
        say(first, project_id, "Bonjour", model)
    with authed(settings) as second:
        assert len(second.get(f"/api/projects/{project_id}").json()["messages"]) == 2


def test_deleting_a_project_keeps_its_agents(client, fake):
    fake.reply = REPLY
    model = local_model(client, fake)
    project_id = project(client)
    say(client, project_id, "Roadmap", model)
    message = client.get(f"/api/projects/{project_id}").json()["messages"][1]
    client.post(f"/api/projects/{project_id}/messages/{message['id']}/approve")
    client.delete(f"/api/projects/{project_id}")
    assert len(client.get("/api/agents").json()) == 1
