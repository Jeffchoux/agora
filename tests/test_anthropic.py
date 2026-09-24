"""Offline transport tests: never use real keys or call a paid model."""

import json

import httpx
import pytest

from agora.config import profiles
from agora.worker import generate


def profile(**changes):
    return {"label": "My Claude API", "provider": "anthropic", "model": "account-model-id", "operator_authorized": True, **changes}


def transport(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only-secret")


@pytest.mark.parametrize("model", ["claude-haiku-4-5", "claude-sonnet-5", "claude-opus-5-5", "claude-fable-5-1", "future-account-model"])
def test_native_messages_and_open_model_id(monkeypatch, model):
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url) == "https://api.anthropic.com/v1/messages"
        assert request.headers["x-api-key"] == "test-only-secret"
        assert request.headers["anthropic-version"] == "2023-06-01"
        body = json.loads(request.content)
        assert body["model"] == model
        assert body["max_tokens"] == 1024
        assert body["messages"] == [{"role": "user", "content": "Review this project"}]
        assert "test-only-secret" not in request.content.decode()
        assert "tools" not in body
        return httpx.Response(200, json={"stop_reason": "end_turn", "content": [{"type": "text", "text": '{"kind":"answer","body":"OK","assessment":null}'}]})

    transport(monkeypatch, handler)
    assert generate(profile(model=model), "Review this project").body == "OK"
    assert len(calls) == 1


@pytest.mark.parametrize("changes, message", [({"operator_authorized": False}, "authorize"), ({"endpoint": "https://example.com/v1"}, "official")])
def test_reject_before_network(monkeypatch, changes, message):
    def forbidden(request):
        pytest.fail("Network request must not run")
    transport(monkeypatch, forbidden)
    with pytest.raises(ValueError, match=message):
        generate(profile(**changes), "hi")


@pytest.mark.parametrize("status", [302, 401, 403, 404, 429, 500])
def test_error_is_sanitized_without_retry(monkeypatch, status):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={"location": "https://example.com"}, json={"error": "test-only-secret"})
    transport(monkeypatch, handler)
    with pytest.raises(ValueError, match=f"HTTP {status}") as error:
        generate(profile(), "hi")
    assert "test-only-secret" not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize("data", [None, {}, {"stop_reason": "max_tokens", "content": []}, {"stop_reason": "tool_use", "content": []}, {"stop_reason": "end_turn", "content": [{"type": "text", "text": "not JSON"}]}, {"stop_reason": "end_turn", "content": [{"type": "tool_use"}]}])
def test_invalid_response_fails_closed(monkeypatch, data):
    transport(monkeypatch, lambda request: httpx.Response(200, content=json.dumps(data)))
    with pytest.raises(ValueError, match="invalid contribution"):
        generate(profile(), "hi")


def test_private_profile_and_cost_classification(tmp_path, monkeypatch):
    from agora.missions import Missions
    from agora.store import Store
    config = tmp_path / "agents.json"
    config.write_text(json.dumps({"my-anthropic": profile()}))
    config.chmod(0o600)
    monkeypatch.setenv("AGORA_AGENTS_FILE", str(config))
    assert profiles({})["my-anthropic"]["model"] == "account-model-id"
    m = Missions(Store(tmp_path / "db"))
    project = m.create_project("API project")
    mid = m.create("Review", "Review this project carefully", ["my-anthropic"], 1, 300, "test", project["id"])
    assert m.detail(mid)["api_budget_usd"] is None
    from fastapi.testclient import TestClient

    from agora.server import create_app
    secret = tmp_path / "admin"
    secret.write_text("private-test-key")
    monkeypatch.setenv("AGORA_ADMIN_TOKEN_FILE", str(secret))
    with TestClient(create_app(tmp_path / "console-db")) as client:
        response = client.get("/v1/console", headers={"Authorization": "Bearer private-test-key"})
        assert response.json()["agents"] == [{"id": "my-anthropic", "label": "My Claude API", "type": "Votre API · tarif du fournisseur"}]
        assert "credential_file" not in response.text
    config.write_text(json.dumps({"my-anthropic": profile(endpoint="https://example.com")}))
    with pytest.raises(ValueError, match="official"):
        profiles({})


def test_subscription_model_choice_never_uses_api_key(monkeypatch):
    from agora.cli_provider import generate_cli
    calls = []
    def execute(argv, prompt, cwd, env, timeout=120):
        calls.append(argv)
        assert "ANTHROPIC_API_KEY" not in env
        if "status" in argv:
            return '{"loggedIn":true,"authMethod":"claude.ai"}'
        assert argv[argv.index("--model") + 1] == "opus"
        assert argv[argv.index("--tools") + 1] == ""
        return '{"is_error":false,"result":"ok"}'
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-be-used")
    monkeypatch.setattr("agora.cli_provider.execute", execute)
    assert generate_cli(profile(provider="claude-cli", model="opus"), "hi", {}) == "ok"
    assert len(calls) == 2


def test_thinking_not_published_and_configurable_token_limit(monkeypatch):
    def handler(request):
        assert json.loads(request.content)["max_tokens"] == 8192
        return httpx.Response(200, json={"stop_reason": "end_turn", "content": [{"type": "thinking", "thinking": "private reasoning"}, {"type": "redacted_thinking", "data": "opaque"}, {"type": "text", "text": '{"kind":"answer","body":"OK"}'}]})
    transport(monkeypatch, handler)
    assert generate(profile(max_tokens=8192), "hi").body == "OK"


@pytest.mark.parametrize("limit", [True, 0, -1, 16385, "1024", None])
def test_token_limit_rejected_before_request(monkeypatch, limit):
    transport(monkeypatch, lambda request: pytest.fail("Unexpected network request"))
    with pytest.raises(ValueError, match="max_tokens"):
        generate(profile(max_tokens=limit), "hi")
