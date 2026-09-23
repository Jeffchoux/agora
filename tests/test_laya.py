import asyncio
import json
import os
import socket
import sys
import threading
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from agora import laya
from agora.laya_service import LocalPredictor, make_server
from agora.server import create_app

TOKEN = "test-only-companion-token-" + "x" * 32
BRIEF = "Review the Python code for bugs and missing tests."


@pytest.fixture
def token_file(tmp_path, monkeypatch):
    path = tmp_path / "companion.key"
    path.write_text(TOKEN)
    path.chmod(0o600)
    monkeypatch.setenv("AGORA_LAYA_TOKEN_FILE", str(path))
    return path


def test_private_token_checks(token_file, tmp_path, monkeypatch):
    assert laya.private_token(token_file) == TOKEN
    assert laya.configured()
    token_file.chmod(0o644)
    assert not laya.configured()
    token_file.chmod(0o600)
    link = tmp_path / "linked"
    link.symlink_to(token_file)
    with pytest.raises(OSError):
        laya.private_token(link)
    for value in ["short", "x" * 513, "hello\n" * 10]:
        token_file.write_text(value)
        assert not laya.configured()
    monkeypatch.delenv("AGORA_LAYA_TOKEN_FILE")
    assert not laya.configured()
    with pytest.raises(ValueError):
        laya.private_token("relative.key")


def test_token_owner_and_missing_config_fail_closed(token_file, monkeypatch):
    actual_uid = os.getuid()
    monkeypatch.setattr(os, "getuid", lambda: actual_uid + 1)
    assert not laya.configured()
    with pytest.raises(laya.Unavailable):
        asyncio.run(laya.LayaBridge().suggest(BRIEF))
    monkeypatch.delenv("AGORA_LAYA_TOKEN_FILE")
    with pytest.raises(laya.Unavailable):
        asyncio.run(laya.LayaBridge().suggest(BRIEF))


@pytest.mark.parametrize("data", [None, [], {}, {"brief": 20}, {"brief": "short"},
    {"brief": "x" * 1201}, {"brief": BRIEF, "url": "http://evil.test"}])
def test_brief_validation(data):
    with pytest.raises(ValueError):
        laya.validate_brief(data)


def transport(monkeypatch, handler):
    original = httpx.AsyncClient

    def factory(**kwargs):
        assert kwargs == {"trust_env": False, "timeout": 15, "follow_redirects": False}
        return original(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(httpx, "AsyncClient", factory)


def test_bridge_fixed_destination_and_allowlisted_response(token_file, monkeypatch):
    def handler(request):
        assert str(request.url) == laya.SUGGEST_URL
        assert request.headers["authorization"] == "Bearer " + TOKEN
        assert json.loads(request.content) == {"brief": BRIEF}
        return httpx.Response(200, json=laya.suggestion("code"))
    transport(monkeypatch, handler)
    assert asyncio.run(laya.LayaBridge().suggest(BRIEF)) == laya.suggestion("code")


@pytest.mark.parametrize("status,payload,error", [
    (302, {}, laya.Unavailable), (500, {}, laya.Unavailable),
    (429, {}, laya.Busy), (400, {}, ValueError),
    (200, {"category": "shell"}, laya.Unavailable),
    (200, {**laya.suggestion("code"), "action": "launch"}, laya.Unavailable),
    (200, ["code"], laya.Unavailable), (200, "x" * 2000, laya.Unavailable),
])
def test_bridge_rejects_failures(token_file, monkeypatch, status, payload, error):
    transport(monkeypatch, lambda _: httpx.Response(status, json=payload))
    bridge = laya.LayaBridge()
    with pytest.raises(error):
        asyncio.run(bridge.suggest(BRIEF))
    assert not bridge.lock.locked()


def test_bridge_timeout_and_busy(token_file, monkeypatch):
    def handler(_request):
        raise httpx.ReadTimeout("sensitive transport detail")
    transport(monkeypatch, handler)
    bridge = laya.LayaBridge()
    with pytest.raises(laya.Unavailable):
        asyncio.run(bridge.suggest(BRIEF))
    bridge.lock.acquire()
    try:
        with pytest.raises(laya.Busy):
            asyncio.run(bridge.suggest(BRIEF))
    finally:
        bridge.lock.release()


def test_console_auth_disabled_and_no_mission_side_effects(token_file, tmp_path, monkeypatch):
    admin = tmp_path / "admin.key"
    admin.write_text("test-operator")
    monkeypatch.setenv("AGORA_ADMIN_TOKEN_FILE", str(admin))
    monkeypatch.setenv("AGORA_LEGACY_INSTALLATION", "0")
    client = TestClient(create_app(tmp_path / "db"))
    endpoint = "/v1/console/laya/suggestions"
    assert client.post(endpoint, json={"brief": BRIEF}).status_code == 401
    headers = {"Authorization": "Bearer test-operator"}
    overview = client.get("/v1/console", headers=headers).json()
    assert overview["laya"] == {"configured": True}
    assert overview["missions"] == []
    # GET neither probes nor loads the model; only POST may contact the bridge.
    transport(monkeypatch, lambda _: httpx.Response(200, json=laya.suggestion("ux")))
    response = client.post(endpoint, headers=headers, json={"brief": BRIEF})
    assert response.status_code == 200
    assert response.json() == laya.suggestion("ux")
    assert client.get("/v1/console", headers=headers).json()["missions"] == []
    assert client.post(endpoint, headers=headers, json={"brief": "a"}).status_code == 400
    monkeypatch.delenv("AGORA_LAYA_TOKEN_FILE")
    assert client.get("/v1/console", headers=headers).json()["laya"] == {"configured": False}
    assert client.post(endpoint, headers=headers, json={"brief": BRIEF}).status_code == 503


@pytest.fixture
def service():
    calls = []
    def predict(brief):
        calls.append(brief)
        if brief.startswith("fail"):
            raise RuntimeError("sensitive details")
        return laya.suggestion("code")
    server = make_server(TOKEN, predict, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address, calls
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_service_auth_input_failures_and_real_http(service, capsys):
    (host, port), calls = service
    assert host == "127.0.0.1"
    with httpx.Client(base_url=f"http://{host}:{port}", trust_env=False) as client:
        assert client.post("/suggest", json={"brief": BRIEF}).status_code == 401
        assert calls == []
        headers = {"Authorization": "Bearer " + TOKEN}
        assert client.post("/other", headers=headers, json={"brief": BRIEF}).status_code == 404
        assert client.post("/suggest", headers=headers, json={"brief": "a"}).status_code == 400
        response = client.post("/suggest", headers=headers, json={"brief": BRIEF})
        assert response.json() == laya.suggestion("code")
        assert calls == [BRIEF]
        response = client.post("/suggest", headers=headers, json={"brief": "fail test request"})
        assert response.status_code == 503
        assert "sensitive" not in response.text
    assert capsys.readouterr().err == ""


def test_service_auth_before_body_and_no_chunked(service):
    address, calls = service
    for authorization, expected in [("wrong", b"401"), (TOKEN, b"400")]:
        with socket.create_connection(address, timeout=2) as conn:
            conn.sendall(("POST /suggest HTTP/1.1\r\nHost: localhost\r\n"
                f"Authorization: Bearer {authorization}\r\n"
                "Transfer-Encoding: chunked\r\n\r\n").encode())
            assert expected in conn.recv(1024).split(b"\r\n")[0]
    assert calls == []


def test_predictor_guard_rejects_truncation_and_invalid_output():
    predictor = LocalPredictor.__new__(LocalPredictor)
    class Tokenizer:
        mask_token = "[MASK]"
        def __call__(self, state, **_kwargs):
            return {"input_ids": list(range(len(state)))}
    agent = SimpleNamespace(tok=Tokenizer(), cfg={"max_len": 1024}, shape={"max_length": 1024})
    agent.prepare = lambda state, _: ([{"ids": list(range(50 + len(state)))}], [])
    agent.predict = lambda *_: {"answers": {"specialty": {"choice": "product"}}}
    predictor.agent = agent
    assert predictor(BRIEF) == laya.suggestion("product")
    with pytest.raises(ValueError):
        predictor("x" * 513)
    agent.prepare = lambda state, _: ([{"ids": list(range(50 + min(10, len(state))))}], [])
    with pytest.raises(ValueError):
        predictor(BRIEF)
    agent.prepare = lambda state, _: ([{"ids": list(range(50 + len(state)))}], [])
    agent.predict = lambda *_: {"answers": {"specialty": {"choice": "execute"}}}
    with pytest.raises(RuntimeError):
        predictor(BRIEF)


def test_predictor_load_is_local_offline_cpu_only(tmp_path, monkeypatch):
    calls = []
    def load(path, **kwargs):
        calls.append((path, kwargs))
        return object()
    monkeypatch.setitem(sys.modules, "laya_coreml", SimpleNamespace(load=load))
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("HF_HUB_DISABLE_TELEMETRY", "0")
    LocalPredictor(tmp_path)
    assert calls == [(str(tmp_path), {"local_files_only": True, "compute_units": "cpu"})]
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"
    with pytest.raises(ValueError):
        LocalPredictor("remote/model-id")
