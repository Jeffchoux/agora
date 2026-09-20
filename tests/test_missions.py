from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from agora.missions import Missions
from agora.server import create_app
from agora.store import Denied, Store
from agora.worker import Contribution


def new(tmp_path):
    m = Missions(Store(tmp_path / "db.sqlite"))
    mid = m.create(
        "Test", "Livrer un objet concret et vérifié.", ["qwen-coder"], 2, 300, "unique"
    )
    return m, mid


def test_reservation_is_atomic_and_budget_survives_reopen(tmp_path):
    m, mid = new(tmp_path)
    m.action(mid, "start")
    m.action(mid, "start")
    with ThreadPoolExecutor(max_workers=4) as pool:
        reservations = list(pool.map(lambda _: m.reserve(), range(4)))
    assert sum(r is not None for r in reservations) == 1
    r = next(r for r in reservations if r)
    m.finish(r["turn"], Contribution(kind="answer", body="ok"))
    reopened = Missions(Store(tmp_path / "db.sqlite"))
    second = reopened.reserve()
    assert second["ordinal"] == 2
    reopened.finish(second["turn"], Contribution(kind="answer", body="ok"))
    assert reopened.reserve() is None
    assert reopened.detail(mid)["calls"] == 2
    assert reopened.detail(mid)["status"] == "finished"
    reopened.action(mid, "start")
    assert reopened.reserve() is None


def test_stop_prevents_next_call_and_keeps_current_result(tmp_path):
    m, mid = new(tmp_path)
    m.action(mid, "start")
    r = m.reserve()
    m.action(mid, "stop")
    m.finish(r["turn"], Contribution(kind="answer", body="done"))
    assert m.reserve() is None
    assert m.detail(mid)["status"] == "stopped"


def test_deadline_and_restart_fail_closed(tmp_path):
    m, mid = new(tmp_path)
    m.action(mid, "start")
    r = m.reserve()
    m.recover()
    assert m.detail(mid)["calls"] == 1
    assert m.detail(mid)["status"] == "failed"
    assert m.reserve() is None
    with pytest.raises(Denied):
        m.finish(r["turn"], Contribution(kind="answer", body="late"))


def test_deadline_never_launches_call_without_time(tmp_path, monkeypatch):
    m, mid = new(tmp_path)
    m.action(mid, "start")
    r = m.reserve()
    m.finish(r["turn"], Contribution(kind="answer", body="ok"))
    with m.store.db() as db:
        db.execute("UPDATE missions SET deadline=0 WHERE id=?", (mid,))
    assert m.reserve() is None
    assert m.detail(mid)["calls"] == 1


def test_no_paid_provider_or_counter_reset(tmp_path):
    m, mid = new(tmp_path)
    with pytest.raises(ValueError):
        m.create("API", "Long enough brief", ["mistral-api"], 1, 300, "paid")
    assert (
        m.create(
            "Test",
            "Livrer un objet concret et vérifié.",
            ["qwen-coder"],
            2,
            300,
            "unique",
        )
        == mid
    )
    with pytest.raises(Denied):
        m.create(
            "Changed",
            "Livrer un objet concret et vérifié.",
            ["qwen-coder"],
            2,
            300,
            "unique",
        )


def test_console_auth_and_input_validation(tmp_path, monkeypatch):
    secret = tmp_path / "admin"
    secret.write_text("private-test-key")
    monkeypatch.setenv("AGORA_ADMIN_TOKEN_FILE", str(secret))
    c = TestClient(create_app(tmp_path / "db.sqlite"))
    assert c.get("/").status_code == 200
    assert c.get("/v1/console").status_code == 401
    headers = {"Authorization": "Bearer private-test-key"}
    assert c.get("/v1/console", headers=headers).status_code == 200
    assert c.post("/v1/console", headers=headers, json=[]).status_code == 400
    payload = {
        "title": "Project",
        "brief": "Build a real project.",
        "agents": ["codex", "grok"],
        "max_calls": 2,
        "seconds": 300,
        "request_key": "request1",
    }
    r = c.post("/v1/console", headers=headers, json=payload)
    assert r.status_code == 200
    mid = r.json()["id"]
    assert (
        c.post("/v1/console/" + mid + "/start", headers=headers, json={}).json()[
            "status"
        ]
        == "queued"
    )
    assert (
        c.post("/v1/console/" + mid + "/start", headers=headers, json={}).json()[
            "calls"
        ]
        == 0
    )
    for invalid in [True, 0, 13]:
        assert (
            c.post(
                "/v1/console",
                headers=headers,
                json={**payload, "max_calls": invalid, "request_key": str(invalid)},
            ).status_code
            == 400
        )
