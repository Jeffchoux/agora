import concurrent.futures

import pytest
from fastapi.testclient import TestClient

from agora.server import create_app
from agora.store import Denied, Store


@pytest.fixture
def board(tmp_path):
    s = Store(tmp_path / "test.sqlite")
    s.create_project("one", "Build a project", max_messages=4, max_depth=2)
    a = s.authenticate(s.invite("one", "codex"))
    b = s.authenticate(s.invite("one", "claude"))
    return s, a, b


def test_question_answer_followup_persists(board):
    s, a, b = board
    q = s.post(a, "claude", "question", "Which schema?", "q")
    r = s.post(b, "codex", "answer", "SQLite with transactions", "r", q["id"])
    s.post(a, "claude", "question", "How do we recover after restart?", "q2", r["id"])
    assert len(Store(s.path).board(a)["messages"]) == 3
    with pytest.raises(Denied):
        s.post(b, "codex", "answer", "Too deep", "r2", s.board(a)["messages"][-1]["id"])


def test_idempotence_conflict_and_budget(board):
    s, a, b = board
    first = s.post(a, "claude", "task", "Build", "same")
    assert s.post(a, "claude", "task", "Build", "same")["id"] == first["id"]
    with pytest.raises(Denied):
        s.post(a, "claude", "task", "Changed", "same")
    for i in range(3):
        s.post(b, "codex", "answer", "answer", str(i))
    with pytest.raises(Denied):
        s.post(b, "codex", "answer", "overflow", "over")


def test_cross_project_and_revoked(board):
    s, a, _b = board
    s.create_project("two", "private")
    c = s.authenticate(s.invite("two", "third"))
    private = s.post(a, "claude", "question", "private data", "q")
    assert s.board(c)["messages"] == []
    with pytest.raises(Denied):
        s.post(c, "codex", "answer", "exfiltrate", "x", private["id"])
    with s.db() as db:
        db.execute("UPDATE members SET enabled=0 WHERE agent=?", ("codex",))
    with pytest.raises(Denied):
        s.board(a)


def test_claim_single_winner(board):
    s, a, b = board
    m = s.post(a, "claude", "task", "Task", "task")

    def claim(_):
        try:
            s.claim(b, m["id"])
            return True
        except Denied:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        assert sum(pool.map(claim, range(6))) == 1
    with pytest.raises(Denied):
        s.claim(a, m["id"])
    with s.db() as db:
        lease = db.execute(
            "SELECT lease FROM claims WHERE message=?", (m["id"],)
        ).fetchone()[0]
    s.claim(b, m["id"], True, lease)
    with pytest.raises(Denied):
        s.claim(b, m["id"])


def test_http_auth_and_body_limit(tmp_path):
    app = create_app(tmp_path / "api.sqlite")
    s = app.state.store
    s.create_project("p", "brief")
    token = s.invite("p", "agent")
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert (
            client.post("/v1/exchange", json={"operation": "board"}).status_code == 401
        )
        headers = {"Authorization": "Bearer " + token}
        assert (
            client.post(
                "/v1/exchange", headers=headers, json={"operation": "board"}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/v1/exchange", headers=headers, content="x" * 70000
            ).status_code
            == 413
        )
        assert client.get("/.well-known/agent-card.json").status_code == 200
