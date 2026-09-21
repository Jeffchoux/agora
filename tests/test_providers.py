import json
from pathlib import Path

import httpx
import pytest

from agora.cli_provider import generate_cli
from agora.worker import generate


def test_free_route_rejects_paid_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    with pytest.raises(ValueError, match="explicit free"):
        generate({"provider": "openrouter-free", "model": "paid/model"}, "hi")


@pytest.mark.parametrize("price", ["0.01", "-1", None])
def test_changed_price_stops_before_generation(monkeypatch, price):
    calls = []

    def handler(request):
        calls.append(request.method)
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "test:free",
                        "pricing": {
                            "prompt": price if price is not None else "1",
                            "completion": "0",
                        },
                    }
                ]
            },
        )

    original = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    with pytest.raises(ValueError, match="currently free"):
        generate({"provider": "openrouter-free", "model": "test:free"}, "hi")
    assert calls == ["GET"]


def test_free_request_has_no_paid_fallback(monkeypatch):
    def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "test:free",
                            "pricing": {"prompt": "0", "completion": "0"},
                        }
                    ]
                },
            )
        body = json.loads(request.content)
        assert body["provider"] == {
            "allow_fallbacks": False,
            "max_price": {"prompt": 0, "completion": 0},
        }
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"kind":"answer","body":"ok"}'}}]
            },
        )

    original = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    assert (
        generate({"provider": "openrouter-free", "model": "test:free"}, "hi").body
        == "ok"
    )


def test_subscription_requires_operator_authorization():
    with pytest.raises(ValueError, match="authorized"):
        generate_cli({"provider": "codex-cli", "model": "x"}, "hi", {})


def test_claude_api_login_cannot_spend(monkeypatch):
    calls = []

    def fake(argv, *args):
        calls.append(argv)
        return '{"loggedIn":true,"authMethod":"api_key"}'

    monkeypatch.setattr("agora.cli_provider.execute", fake)
    with pytest.raises(ValueError, match="subscription login"):
        generate_cli(
            {"provider": "claude-cli", "model": "haiku", "operator_authorized": True},
            "hi",
            {},
        )
    assert len(calls) == 1


def test_credentials_file_is_private_and_selective(tmp_path, monkeypatch):
    from agora.worker import provider_key

    p = tmp_path / "keys.json"
    p.write_text('{"MISTRAL_API_KEY":"selected","UNRELATED_SECRET":"other"}')
    p.chmod(0o600)
    monkeypatch.setenv("MISTRAL_API_KEY", "wrong")
    assert (
        provider_key({"credential_file": str(p), "key_env": "MISTRAL_API_KEY"})
        == "selected"
    )
    p.chmod(0o644)
    with pytest.raises(ValueError, match="private"):
        provider_key({"credential_file": str(p), "key_env": "MISTRAL_API_KEY"})


def test_missing_selected_key_has_no_environment_fallback(tmp_path, monkeypatch):
    from agora.worker import provider_key

    p = tmp_path / "keys.json"
    p.write_text("{}")
    p.chmod(0o600)
    monkeypatch.setenv("MISTRAL_API_KEY", "must-not-fallback")
    with pytest.raises(ValueError, match="missing"):
        provider_key({"credential_file": str(p), "key_env": "MISTRAL_API_KEY"})


def test_grok_structured_output_and_no_tools(monkeypatch):
    from agora.cli_provider import generate_cli

    def fake(argv, prompt, cwd, env):
        assert argv[argv.index("--tools") + 1] == ""
        assert "--no-subagents" in argv and "--disable-web-search" in argv
        assert "--system-prompt-override" in argv
        assert "XAI_API_KEY" not in env
        return '{"structuredOutput":{"kind":"answer","body":"ok"}}'

    monkeypatch.setenv("XAI_API_KEY", "must-not-be-used")
    monkeypatch.setattr("agora.cli_provider.execute", fake)
    assert (
        json.loads(
            generate_cli(
                {
                    "provider": "grok-cli",
                    "model": "default",
                    "operator_authorized": True,
                },
                "hello",
                {},
            )
        )["body"]
        == "ok"
    )


def test_codex_receives_only_explicit_mission_capture(tmp_path, monkeypatch):
    capture = tmp_path / "320.png"
    capture.write_bytes(b"PNG")
    seen = []

    def fake(argv, _prompt, _cwd, _env, _timeout=120):
        if argv[:3] == ["codex", "login", "status"]:
            return "Logged in using ChatGPT"
        seen.extend(argv)
        Path(argv[argv.index("--output-last-message") + 1]).write_text(
            '{"kind":"answer","body":"capture reçue"}'
        )
        return '{"item":{}}'

    monkeypatch.setattr("agora.cli_provider.execute", fake)
    result = generate_cli(
        {"provider": "codex-cli", "model": "gpt-6-astra", "operator_authorized": True},
        "Observe la capture",
        {},
        images=[capture],
    )
    assert json.loads(result)["kind"] == "answer"
    assert seen[seen.index("--image") + 1] == str(capture)
    with pytest.raises(ValueError, match="invalid mission capture"):
        generate_cli(
            {"provider": "codex-cli", "model": "gpt-6-astra", "operator_authorized": True},
            "Observe la capture",
            {},
            images=[tmp_path / "missing.png"],
        )
