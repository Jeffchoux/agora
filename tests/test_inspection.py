import base64

import pytest
from fastapi.testclient import TestClient

from agora import inspection, mission_runner
from agora.missions import Missions
from agora.server import create_app
from agora.store import Denied, Store
from agora.worker import Contribution


def test_repository_evidence_is_pinned_and_bounded(monkeypatch):
    sha = "a" * 40
    blob_sha = "b" * 40
    calls = []

    def github(path):
        calls.append(path)
        if path.endswith("/commits/main"):
            return {"sha": sha}
        if "/git/trees/" in path:
            return {"tree": [{"path": "README.md", "type": "blob", "sha": blob_sha, "size": 20}]}
        if "/git/blobs/" in path:
            return {"encoding": "base64", "content": base64.b64encode(b"Real code\n").decode()}
        return {"check_runs": [{"name": "tests", "status": "completed", "conclusion": "success"}]}

    monkeypatch.setattr(inspection, "_github_json", github)
    evidence = inspection._repository(inspection.TARGETS["boostmybiz"])
    assert evidence["github_sha"] == sha
    assert evidence["files"] == [
        {"path": "README.md", "blob_sha": blob_sha, "excerpt": "1: Real code"}
    ]
    assert evidence["checks"][0]["conclusion"] == "success"
    assert all("secret" not in path for path in calls)


def test_runner_collects_once_before_model_reservation(tmp_path):
    calls = []

    def collector(target, path):
        calls.append((target, path))
        return {"target": target, "github_sha": "a" * 40, "browser": []}

    missions = Missions(Store(tmp_path / "db.sqlite"), collector=collector)
    mid = missions.create("Audit", "Vérifier le vrai site.", ["codex"], 1, 300, "one", "boostmybiz")
    assert missions.detail(mid)["evidence"] is None
    missions.action(mid, "start")
    missions.action(mid, "start")
    assert missions.detail(mid)["status"] == "queued"
    assert missions.reserve() is None
    assert missions.prepare_next()
    assert not missions.prepare_next()
    assert len(calls) == 1
    assert missions.detail(mid)["evidence"]["github_sha"] == "a" * 40
    assert missions.reserve()["evidence"]["target"] == "boostmybiz"
    reopened = Missions(Store(tmp_path / "db.sqlite"), collector=collector)
    assert reopened.detail(mid)["target"] == "boostmybiz"
    with pytest.raises(Denied):
        reopened.create("Audit", "Vérifier le vrai site.", ["codex"], 1, 300, "one", None)


def test_failed_inspection_never_queues_model(tmp_path):
    def unavailable(_target, _path):
        raise ValueError("credential details must stay private")

    missions = Missions(Store(tmp_path / "db.sqlite"), collector=unavailable)
    mid = missions.create("Audit", "Vérifier le vrai site.", ["codex"], 1, 300, "two", "boostmybiz")
    missions.action(mid, "start")
    assert missions.prepare_next()
    assert missions.detail(mid)["status"] == "failed"
    assert "credential" not in missions.detail(mid)["error"]
    assert missions.reserve() is None


def test_console_screenshot_requires_operator_and_recorded_evidence(tmp_path, monkeypatch):
    secret = tmp_path / "operator.key"
    secret.write_text("private-test-key")
    monkeypatch.setenv("AGORA_ADMIN_TOKEN_FILE", str(secret))
    store = Store(tmp_path / "db.sqlite")
    missions = Missions(store, collector=lambda _target, _path: {"browser": [{"viewport": 320, "screenshot": "320.png"}]})
    mid = missions.create("Audit", "Vérifier le vrai site.", ["codex"], 1, 300, "three", "boostmybiz")
    missions.action(mid, "start")
    missions.prepare_next()
    screenshot = tmp_path / "evidence" / mid / "320.png"
    screenshot.parent.mkdir(parents=True)
    screenshot.write_bytes(b"PNG")
    client = TestClient(create_app(tmp_path / "db.sqlite"))
    url = f"/v1/console/{mid}/evidence/320"
    assert client.get(url).status_code == 401
    assert client.get(url, headers={"Authorization": "Bearer private-test-key"}).content == b"PNG"
    assert client.get(url.replace("320", "768"), headers={"Authorization": "Bearer private-test-key"}).status_code == 404


def test_only_registered_target_is_accepted(tmp_path):
    missions = Missions(Store(tmp_path / "db.sqlite"))
    with pytest.raises(ValueError, match="Projet non connecté"):
        missions.create("Audit", "Vérifier le vrai site.", ["codex"], 1, 300, "four", "https://127.0.0.1/")


def test_agents_exchange_evidence_based_questions_and_answers(tmp_path, monkeypatch):
    def collector(_target, capture_dir):
        capture_dir.mkdir(parents=True)
        (capture_dir / "320.png").write_bytes(b"PNG")
        return {"github_sha": "a" * 40, "browser": [{"viewport": 320, "screenshot": "320.png"}]}

    calls = []

    def model(_profile, prompt, images=()):
        calls.append((prompt, images))
        return Contribution(kind="question" if len(calls) == 1 else "answer", body="Preuve et question" if len(calls) == 1 else "Réponse appuyée sur la preuve")

    monkeypatch.setattr(mission_runner, "generate", model)
    missions = Missions(Store(tmp_path / "db.sqlite"), collector=collector)
    mid = missions.create("Audit", "Vérifier le vrai site.", ["codex", "qwen-coder"], 2, 300, "five", "boostmybiz")
    missions.action(mid, "start")
    assert mission_runner.step(missions)  # Evidence first, no model call.
    assert not calls
    assert mission_runner.step(missions)
    assert mission_runner.step(missions)
    assert missions.detail(mid)["status"] == "finished"
    assert [turn["kind"] for turn in missions.detail(mid)["turns"]] == ["question", "answer"]
    assert "a" * 40 in calls[0][0]
    assert calls[0][1] == [tmp_path / "evidence" / mid / "320.png"]
    assert calls[1][1] == []
