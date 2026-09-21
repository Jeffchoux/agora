import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agora import mission_runner
from agora.decisions import Assessment, source_catalog
from agora.missions import Missions
from agora.server import create_app
from agora.store import Denied, Store
from agora.worker import Contribution, contribution_schema


def assessment(verdict="revise", references=None):
    return {"verdict": verdict, "rationale": "The sample leaves an open question.",
            "next_check": "Inspect the missing scenario.", "references": references or []}


def new(tmp_path, agents=None, calls=2, question="Can we ship this change?"):
    missions = Missions(Store(tmp_path / "db.sqlite"))
    mid = missions.create("Review", "Review the proposed change.", agents or ["qwen-coder", "llama"],
                          calls, 600, "decision", decision_question=question)
    return missions, mid


def contribute(missions, verdict="revise", references=None, absent=False):
    reservation = missions.reserve()
    missions.finish(reservation["turn"], Contribution(
        kind=reservation["expected_kind"], body="A bounded contribution.",
        assessment=None if absent else assessment(verdict, references)))
    return reservation


@pytest.mark.parametrize("changes", [
    {"verdict": "approved"}, {"verdict": 1}, {"rationale": " "},
    {"rationale": "x" * 801}, {"next_check": ""}, {"next_check": "x" * 501},
    {"next_check": 123}, {"references": ["x"] * 9}, {"references": ["x" * 513]},
    {"references": [""]}, {"references": [1]}, {"references": "file:a"},
    {"confidence": 0.9}, {"votes": 3}, {"probability": 1},
])
def test_assessment_rejects_malformed_output(changes):
    with pytest.raises(ValidationError):
        Contribution(kind="review", body="Review", assessment=assessment() | changes)


def test_legacy_contribution_and_whitespace():
    assert Contribution(kind="review", body="Legacy").assessment is None
    value = Assessment(**(assessment() | {"rationale": "  Reason  ", "next_check": "  Check  "}))
    assert value.rationale == "Reason"
    assert value.next_check == "Check"
    schema = contribution_schema()
    assert set(schema["required"]) == set(schema["properties"])
    assert {"type": "null"} in schema["properties"]["assessment"]["anyOf"]
    assert "default" not in schema["properties"]["assessment"]


def test_catalog_only_collected_sources():
    evidence = {"github_sha": "a" * 40, "repository": "owner/repo", "website": "https://example.org",
                "files": [{"path": "src/a.py"}, {"path": "src/a.py"}, {"path": "x" * 508}],
                "browser": [{"viewport": 320, "http_status": 404},
                            {"viewport": 768, "http_status": 200, "error": "Timeout"},
                            {"viewport": 1440}, {"viewport": 999, "http_status": 200}]}
    assert source_catalog(evidence) == [
        {"id": "commit:" + "a" * 40, "label": "Commit " + "a" * 40},
        {"id": "file:src/a.py", "label": "src/a.py"},
        {"id": "view:320", "label": "Browser observation 320 px"},
    ]
    assert source_catalog(None) == []
    assert source_catalog({"github_sha": "invented"}) == []


def test_legacy_migration_concurrent_and_idempotent(tmp_path):
    missions, mid = new(tmp_path, question="")
    missions.action(mid, "start")
    contribute(missions, absent=True)
    with missions.store.db() as db:
        db.execute("ALTER TABLE missions DROP COLUMN decision_question")
        db.execute("ALTER TABLE mission_turns DROP COLUMN assessment")
    with ThreadPoolExecutor(max_workers=3) as pool:
        copies = list(pool.map(lambda _: Missions(Store(tmp_path / "db.sqlite")), range(3)))
    for copy in copies:
        detail = copy.detail(mid)
        assert detail["decision_question"] == ""
        assert detail["decision"] is None
        assert detail["calls"] == 1
        assert detail["turns"][0]["assessment"] is None
        assert copy.create("Review", "Review the proposed change.", ["qwen-coder", "llama"],
                           2, 600, "decision") == mid


def test_decision_question_validation_and_idempotency(tmp_path):
    missions, mid = new(tmp_path, question="  Can we ship this change?  ")
    assert missions.detail(mid)["decision"]["question"] == "Can we ship this change?"
    assert missions.create("Review", "Review the proposed change.", ["qwen-coder", "llama"], 2,
                           600, "decision", decision_question="Can we ship this change?") == mid
    with pytest.raises(Denied, match="Conflit"):
        missions.create("Review", "Review the proposed change.", ["qwen-coder", "llama"], 2,
                        600, "decision", decision_question="Different question?")
    for value in (None, 2, [], "x" * 501):
        with pytest.raises(ValueError, match="Decision question"):
            missions.create("Review", "Review the proposed change.", ["qwen-coder"], 1,
                            600, "bad", decision_question=value)


def test_latest_position_per_selected_agent_not_votes(tmp_path):
    missions, mid = new(tmp_path, calls=4)
    assert missions.detail(mid)["decision"]["positions"] == [
        {"agent": agent, "turn_id": None, "status": "pending", "assessment": None}
        for agent in ["qwen-coder", "llama"]]
    missions.action(mid, "start")
    first = contribute(missions, "proceed")
    assert missions.detail(mid)["decision"]["agreement"] == "none"
    contribute(missions, "revise")
    assert missions.detail(mid)["decision"]["agreement"] == "mixed"
    third = contribute(missions, "revise")
    current = missions.detail(mid)["decision"]
    assert current["agreement"] == "aligned" and not current["complete"]
    assert current["positions"][0]["turn_id"] == third["turn"] != first["turn"]
    running = missions.reserve()
    current = missions.detail(mid)["decision"]
    assert current["agreement"] == "none" and current["positions"][1]["assessment"] is None
    missions.finish(running["turn"], Contribution(kind="answer", body="Answer", assessment=assessment()))
    current = missions.detail(mid)["decision"]
    assert current["complete"] and current["agreement"] == "aligned"
    assert len(current["positions"]) == 2


@pytest.mark.parametrize("ending", ["missing", "failed", "stopped", "mixed"])
def test_completion_is_not_agreement_or_approval(tmp_path, ending):
    missions, mid = new(tmp_path)
    missions.action(mid, "start")
    contribute(missions)
    if ending == "failed":
        missions.finish(missions.reserve()["turn"])
    else:
        if ending == "stopped":
            reservation = missions.reserve()
            missions.action(mid, "stop")
            missions.finish(reservation["turn"], Contribution(kind="answer", body="Answer", assessment=assessment()))
        else:
            contribute(missions, "proceed" if ending == "mixed" else "revise", absent=ending == "missing")
    decision = missions.detail(mid)["decision"]
    assert decision["complete"] is (ending == "mixed")
    assert decision["agreement"] == {"mixed": "mixed", "stopped": "aligned"}.get(ending, "none")
    assert "approved" not in decision and "confidence" not in decision


def test_invalid_reference_rejected_before_write_and_runner_fails_closed(tmp_path, monkeypatch):
    missions, mid = new(tmp_path)
    missions.action(mid, "start")
    reservation = missions.reserve()
    bad = Contribution(kind="question", body="Question", assessment=assessment(references=["file:invented.py"]))
    with pytest.raises(ValueError, match="collected sources"):
        missions.finish(reservation["turn"], bad)
    detail = missions.detail(mid)
    assert detail["calls"] == 1
    assert detail["turns"][0]["status"] == "running"
    assert detail["turns"][0]["assessment"] is None
    missions.finish(reservation["turn"])
    second = missions.create("Review 2", "Review this proposed change.", ["qwen-coder"], 1, 600, "second", decision_question="Ship?")
    missions.action(second, "start")
    monkeypatch.setattr(mission_runner, "generate", lambda *_args, **_kwargs: bad.model_copy(update={"kind": "review"}))
    assert mission_runner.step(missions)
    detail = missions.detail(second)
    assert detail["status"] == "failed" and detail["calls"] == 1
    assert detail["turns"][0]["assessment"] is None
    assert not mission_runner.step(missions)


@pytest.mark.parametrize("brief", ["Review this change in English.", "Examine ce changement en français."])
def test_prompt_requests_typed_position_without_more_calls(tmp_path, monkeypatch, brief):
    evidence = {"files": [{"path": "a.py", "excerpt": "pass"}], "browser": [], "github_sha": "a" * 40}
    missions = Missions(Store(tmp_path / "db.sqlite"), collector=lambda *_args: evidence)
    project = missions.create_project("Example")
    mid = missions.create("Review", brief, ["qwen-coder"], 1, 600, "prompt", project["id"], "Can we ship?")
    calls = []

    def generate(_profile, prompt, images=()):
        calls.append(prompt)
        return Contribution(kind="review", body="Review", assessment=assessment(references=["file:a.py"]))

    monkeypatch.setattr(mission_runner, "generate", generate)
    missions.action(mid, "start")
    assert mission_runner.step(missions) and not calls
    assert mission_runner.step(missions) and len(calls) == 1
    assert not mission_runner.step(missions)
    instructions, payload = calls[0].split("Data:\n", 1)
    context = json.loads(payload)
    assert context["brief"] == brief and context["decision_question"] == "Can we ship?"
    assert context["source_catalog"] == source_catalog(evidence)
    assert "Use the brief language for all prose" in instructions
    assert "not approval or an instruction to act" in instructions
    assert "not support for a claim" in instructions
    assert "kind=review" in instructions
    detail = missions.detail(mid)
    assert detail["decision"]["complete"]
    assert detail["turns"][0]["assessment"]["references"] == ["file:a.py"]


def test_console_decision_contract(tmp_path, monkeypatch):
    secret = tmp_path / "operator.key"
    secret.write_text("test-key")
    secret.chmod(0o600)
    monkeypatch.setenv("AGORA_ADMIN_TOKEN_FILE", str(secret))
    client = TestClient(create_app(tmp_path / "db.sqlite"))
    headers = {"Authorization": "Bearer test-key"}
    payload = {"title": "Review", "brief": "Review the proposed change.", "agents": ["qwen-coder"],
               "max_calls": 1, "seconds": 600, "request_key": "api", "decision_question": "  Ship?  "}
    response = client.post("/v1/console", json=payload, headers=headers)
    assert response.status_code == 200
    mid = response.json()["id"]
    detail = client.get(f"/v1/console/{mid}", headers=headers).json()
    assert detail["decision_question"] == detail["decision"]["question"] == "Ship?"
    assert detail["decision"]["agreement"] == "none" and not detail["decision"]["complete"]
    assert client.get(f"/v1/console/{mid}").status_code == 401
    assert client.post("/v1/console", json=payload | {"decision_question": "x" * 501}, headers=headers).status_code == 400


def test_second_agent_receives_actual_first_assessment(tmp_path, monkeypatch):
    missions, mid = new(tmp_path)
    first_position = assessment("insufficient_evidence") | {
        "rationale": "The repository was not supplied, so the expiry guard cannot be checked.",
        "next_check": "Supply the invitation handler and expired-invitation test result.",
    }
    prompts = []

    def generate(_profile, prompt, images=()):
        prompts.append(json.loads(prompt.split("Data:\n", 1)[1]))
        return Contribution(
            kind="question" if len(prompts) == 1 else "answer",
            body="What evidence do we need?" if len(prompts) == 1 else "Inspect the handler.",
            assessment=first_position if len(prompts) == 1 else assessment(),
        )

    monkeypatch.setattr(mission_runner, "generate", generate)
    missions.action(mid, "start")
    assert mission_runner.step(missions)
    assert mission_runner.step(missions)
    assert not mission_runner.step(missions)
    assert len(prompts) == 2
    assert prompts[0]["previous"] == []
    previous = prompts[1]["previous"]
    assert len(previous) == 1 and previous[0]["agent"] == "qwen-coder"
    assert previous[0]["assessment"] == first_position
    assert previous[0]["assessment_abbreviated"] is False
    assert previous[0]["assessment"] == missions.detail(mid)["turns"][0]["assessment"]


@pytest.mark.parametrize("character", ["R", "\x00"])
def test_assessment_history_stays_bounded_and_does_not_invent_references(tmp_path, character):
    missions, mid = new(tmp_path, calls=6)
    missions.action(mid, "start")
    for _ in range(4):
        contribute(missions)
    prior = missions.reserve()["previous"]
    assert len(prior) == 3
    assert all(isinstance(item["assessment"], dict) for item in prior)
    original = assessment() | {"rationale": character * 800, "next_check": character * 500,
                               "references": ["file:" + "x" * 507, "file:short.py"]}
    compact = mission_runner.previous_context({"agent": "qwen-coder", "kind": "question",
                                               "body": "B" * 1500, "assessment": original})
    assert compact["assessment_abbreviated"] is True
    assert compact["assessment"]["references"] == ["file:short.py"]
    assert original["rationale"].startswith(compact["assessment"]["rationale"])
    assert original["next_check"].startswith(compact["assessment"]["next_check"])
    assert len(compact["body"]) + len(json.dumps(compact["assessment"], ensure_ascii=False)) <= 1500
