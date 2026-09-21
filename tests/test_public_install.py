import json

import pytest

from agora import inspection
from agora.missions import Missions
from agora.store import Store


def test_fresh_install_has_no_personal_project_or_authorized_agent(tmp_path, monkeypatch):
    monkeypatch.delenv("AGORA_LEGACY_INSTALLATION")
    missions = Missions(Store(tmp_path / "db"))
    assert missions.projects() == []
    assert missions.profiles == {}
    with pytest.raises(ValueError):
        missions.create("Test", "A sufficiently long brief", ["codex"], 1, 300, "1")


def test_description_only_projects_chat_and_context(tmp_path):
    m = Missions(Store(tmp_path / "db"))
    first = m.create_project("Idea one")
    second = m.create_project("Idea two")
    assert first["id"] != second["id"]
    m.post_chat(first["id"], "Create a community garden", "message-1")
    m.post_chat(first["id"], "Create a community garden", "message-1")
    assert len(m.chat(first["id"])) == 1
    assert m.chat(second["id"]) == []
    mid = m.create("Plan", "Discuss feasibility together", ["qwen-coder"], 1, 300, "m", first["id"])
    m.action(mid, "start")
    assert m.prepare_next()
    r = m.reserve()
    assert r["project_chat"] == [{"body": "Create a community garden"}]
    assert r["evidence"]["repository"] is None
    assert r["evidence"]["browser"] == []


def test_optional_sources_do_not_invoke_unconfigured_collectors(tmp_path, monkeypatch):
    def forbidden(*args):
        raise AssertionError("unconfigured source called")
    monkeypatch.setattr(inspection, "_repository", forbidden)
    monkeypatch.setattr(inspection, "_browser", lambda *_: [{"viewport": 320}])
    result = inspection.collect({"id": "x", "custom": True, "repository": None, "website": "https://example.com"}, tmp_path)
    assert result["repository"] is None
    assert result["browser"] == [{"viewport": 320}]


def test_own_api_configuration_is_explicit_and_private(tmp_path, monkeypatch):
    file = tmp_path / "agents.json"
    profile = {"label": "My API", "provider": "openai-compatible", "model": "chosen-model", "endpoint": "https://api.example/v1", "operator_authorized": True, "key_env": "MY_KEY"}
    file.write_text(json.dumps({"my-api": profile}))
    file.chmod(0o600)
    monkeypatch.setenv("AGORA_AGENTS_FILE", str(file))
    m = Missions(Store(tmp_path / "db"))
    assert list(m.profiles) == ["my-api"]
    profile["operator_authorized"] = False
    file.write_text(json.dumps({"my-api": profile}))
    with pytest.raises(ValueError, match="authorization"):
        Missions(m.store)
    file.chmod(0o644)
    with pytest.raises(ValueError, match="private"):
        Missions(m.store)


def test_migration_preserves_existing_projects(tmp_path):
    store = Store(tmp_path / "db")
    with store.db() as db:
        db.execute("CREATE TABLE console_projects(id TEXT PRIMARY KEY,label TEXT NOT NULL,repository TEXT NOT NULL,website TEXT NOT NULL,notes TEXT NOT NULL,created REAL NOT NULL,UNIQUE(repository,website))")
        db.execute("INSERT INTO console_projects VALUES('old','Old','owner/repo','https://example.com','Keep me',1)")
    m = Missions(store)
    assert m.project("old")["notes"] == "Keep me"
    assert m.create_project("New idea")["repository"] is None
