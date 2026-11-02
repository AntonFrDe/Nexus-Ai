import pytest
from fake_provider import API_KEY, start_fake_provider

from nexus.nodes.config_model import validate_config
from nexus.providers.capabilities import capabilities_from_parameters, parameter_fields
from nexus.providers.catalog import PROVIDER_TYPES
from nexus.workflows.schemas import WorkflowGraph


@pytest.fixture
def fake():
    server = start_fake_provider()
    yield server
    server.shutdown()


def base_url(server) -> str:
    return f"http://127.0.0.1:{server.server_address[1]}"


def ollama(client, fake) -> dict:
    response = client.post(
        "/api/providers", json={"type": "ollama", "name": "Local", "endpoint": base_url(fake)}
    )
    assert response.status_code == 201, response.text
    return response.json()


def hosted(client, fake) -> dict:
    client.put("/api/secrets/hosted.key", json={"value": API_KEY})
    response = client.post(
        "/api/providers",
        json={
            "type": "openai_compatible",
            "name": "Hosted",
            "endpoint": f"{base_url(fake)}/v1",
            "secret_name": "hosted.key",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_every_required_provider_type_is_listed(client):
    ids = {item["id"] for item in client.get("/api/provider-types").json()}
    assert ids == {
        "anthropic", "openai", "gemini", "mistral", "openrouter", "ollama", "lm_studio",
        "litellm_gateway", "openai_compatible",
    }  # fmt: skip
    assert all(not item.local or not item.paid for item in PROVIDER_TYPES)


def test_default_endpoints_and_required_ones(client):
    created = client.post("/api/providers", json={"type": "ollama", "name": "A"}).json()
    assert created["endpoint"] == "http://127.0.0.1:11434"
    refused = client.post("/api/providers", json={"type": "openai_compatible", "name": "B"})
    assert refused.status_code == 409
    assert client.post("/api/providers", json={"type": "nope", "name": "C"}).status_code == 409
    bad = {"type": "ollama", "name": "D", "endpoint": "file:///etc/passwd"}
    assert client.post("/api/providers", json=bad).status_code == 422


def test_names_are_unique(client):
    client.post("/api/providers", json={"type": "ollama", "name": "A"})
    response = client.post("/api/providers", json={"type": "ollama", "name": "A"})
    assert response.status_code == 409


def test_providers_expose_a_reference_never_the_key(client, fake):
    provider = hosted(client, fake)
    assert provider["secret_name"] == "hosted.key"
    assert provider["has_secret"] is True
    assert API_KEY not in client.get(f"/api/providers/{provider['id']}").text
    assert (
        client.post(
            "/api/providers",
            json={"type": "openai", "name": "x", "api_key": API_KEY},
        ).status_code
        == 422
    )


def test_local_connection_and_discovery(client, fake):
    provider = ollama(client, fake)
    result = client.post(f"/api/providers/{provider['id']}/test").json()
    assert result["ok"] is True
    assert result["models_found"] == 1
    models = client.post(f"/api/providers/{provider['id']}/discover").json()
    assert [model["model_id"] for model in models] == ["local-coder:latest"]
    assert models[0]["source"] == "discovered"
    assert models[0]["capabilities"]["tool_calling"] is True
    assert models[0]["capabilities"]["top_k"] is True


def test_real_call_through_litellm_to_a_local_server(client, fake):
    provider = ollama(client, fake)
    model = client.post(f"/api/providers/{provider['id']}/discover").json()[0]
    result = client.post(f"/api/models/{model['id']}/test", json={}).json()
    assert result["ok"] is True, result
    assert result["text"] == "ready"
    assert result["output_tokens"] == 1
    assert fake.requests[0]["path"] == "/api/chat"
    stored = client.get("/api/models").json()[0]
    assert stored["last_test"]["ok"] is True


def test_paid_calls_need_confirmation_and_send_the_key(client, fake):
    provider = hosted(client, fake)
    model = client.post(f"/api/providers/{provider['id']}/discover").json()[0]
    url = f"/api/models/{model['id']}/test"
    assert client.post(url, json={}).status_code == 409
    assert fake.requests == []
    result = client.post(url, json={"confirm_paid": True}).json()
    assert result["ok"] is True, result
    assert result["served_by"]


def test_failures_are_reported_and_keys_are_scrubbed(client, fake):
    client.put("/api/secrets/wrong", json={"value": "sk-wrong-value"})
    provider = client.post(
        "/api/providers",
        json={
            "type": "openai_compatible",
            "name": "Wrong",
            "endpoint": f"{base_url(fake)}/v1",
            "secret_name": "wrong",
        },
    ).json()
    result = client.post(f"/api/providers/{provider['id']}/test").json()
    assert result["ok"] is False
    assert "401" in result["message"]
    model = client.post(
        f"/api/providers/{provider['id']}/models", json={"model_id": "hosted-model"}
    ).json()
    outcome = client.post(f"/api/models/{model['id']}/test", json={"confirm_paid": True}).json()
    assert outcome["ok"] is False
    assert "sk-wrong-value" not in outcome["message"]


def test_unreachable_and_unconfigured_providers_stay_usable(client):
    down = client.post(
        "/api/providers",
        json={
            "type": "ollama",
            "name": "Down",
            "endpoint": "http://127.0.0.1:1",
            "timeout_seconds": 1,
        },
    ).json()
    assert client.post(f"/api/providers/{down['id']}/test").json()["ok"] is False
    assert client.post(f"/api/providers/{down['id']}/discover").status_code == 502
    nokey = client.post("/api/providers", json={"type": "openai", "name": "NoKey"}).json()
    result = client.post(f"/api/providers/{nokey['id']}/test").json()
    assert "no API key" in result["message"]


def test_disabled_providers_make_no_calls(client, fake):
    provider = ollama(client, fake)
    model = client.post(f"/api/providers/{provider['id']}/discover").json()[0]
    client.patch(f"/api/providers/{provider['id']}", json={"enabled": False})
    result = client.post(f"/api/models/{model['id']}/test", json={}).json()
    assert result["ok"] is False
    assert fake.requests == []


def test_parameters_follow_capabilities():
    supported = capabilities_from_parameters(["temperature", "stream"], top_k=False)
    assert supported["temperature"] and supported["streaming"]
    assert not supported["tool_calling"]
    names = [field.name for field in parameter_fields(supported)]
    assert names == ["temperature"]
    problems = validate_config("t", parameter_fields(supported), {"top_p": 0.5})
    assert problems


def test_unsupported_defaults_are_refused_and_overrides_change_that(client, fake):
    provider = ollama(client, fake)
    model = client.post(f"/api/providers/{provider['id']}/discover").json()[0]
    url = f"/api/models/{model['id']}"
    assert client.patch(url, json={"defaults": {"temperature": 0.3}}).status_code == 200
    assert client.patch(url, json={"defaults": {"temperature": 9}}).status_code == 409
    assert client.patch(url, json={"defaults": {"invented": 1}}).status_code == 409

    off = {"capability_overrides": {"temperature": False}, "defaults": {}}
    updated = client.patch(url, json=off).json()
    assert "temperature" not in [field["name"] for field in updated["parameter_fields"]]
    assert client.patch(url, json={"defaults": {"temperature": 0.3}}).status_code == 409
    assert client.patch(url, json={"capability_overrides": {"nope": True}}).status_code == 409


def test_defaults_reach_the_model_call(client, fake):
    provider = ollama(client, fake)
    model = client.post(f"/api/providers/{provider['id']}/discover").json()[0]
    client.patch(f"/api/models/{model['id']}", json={"defaults": {"temperature": 0.25}})
    client.post(f"/api/models/{model['id']}/test", json={})
    assert fake.requests[0]["body"]["options"]["temperature"] == 0.25


def test_rediscovery_keeps_manual_corrections(client, fake):
    provider = ollama(client, fake)
    url = f"/api/providers/{provider['id']}/discover"
    model = client.post(url).json()[0]
    client.patch(
        f"/api/models/{model['id']}",
        json={"capability_overrides": {"tool_calling": False}, "context_window": 32000},
    )
    again = client.post(url).json()[0]
    assert again["id"] == model["id"]
    assert again["capabilities"]["tool_calling"] is False
    assert again["context_window"] == 32000


def test_manual_models_for_providers_without_listing(client):
    client.put("/api/secrets/g", json={"value": "k"})
    provider = client.post(
        "/api/providers", json={"type": "gemini", "name": "G", "secret_name": "g"}
    ).json()
    result = client.post(f"/api/providers/{provider['id']}/test").json()
    assert "test a model" in result["message"]
    model = client.post(
        f"/api/providers/{provider['id']}/models",
        json={"model_id": "gemini-2.5-flash"},
    )
    assert model.status_code == 201
    assert model.json()["capabilities"]["reasoning_effort"] is True
    duplicate = client.post(
        f"/api/providers/{provider['id']}/models",
        json={"model_id": "gemini-2.5-flash"},
    )
    assert duplicate.status_code == 409


def test_deleting_a_provider_removes_its_models(client, fake):
    provider = ollama(client, fake)
    client.post(f"/api/providers/{provider['id']}/discover")
    assert client.delete(f"/api/providers/{provider['id']}").status_code == 204
    assert client.get("/api/models").json() == []


def test_api_key_never_appears_in_a_workflow_model_field():
    graph = WorkflowGraph.model_validate({"nodes": []})
    assert "secret" not in graph.model_dump_json()
