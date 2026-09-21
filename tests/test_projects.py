import base64
import socket

import pytest
from fastapi.testclient import TestClient

from agora import inspection
from agora.missions import Missions
from agora.server import create_app
from agora.store import Store


def test_operator_can_register_and_switch_projects(tmp_path, monkeypatch):
    secret = tmp_path / "operator.key"
    secret.write_text("private-test-key")
    monkeypatch.setenv("AGORA_ADMIN_TOKEN_FILE", str(secret))
    client = TestClient(create_app(tmp_path / "db.sqlite"))
    headers = {"Authorization": "Bearer private-test-key"}
    payload = {
        "label": "Ricky Club",
        "repository": "https://github.com/Jeffchoux/ricky-club",
        "website": "https://ricky-club.example/club",
        "notes": "Vérifier le parcours d’adhésion sans soumettre le formulaire.",
    }
    assert client.post("/v1/console/projects", json=payload).status_code == 401
    created = client.post("/v1/console/projects", headers=headers, json=payload)
    assert created.status_code == 200
    project = created.json()
    assert project["repository"] == "Jeffchoux/ricky-club"
    assert project["website"] == "https://ricky-club.example/club"
    assert client.post("/v1/console/projects", headers=headers, json=payload).json()["id"] == project["id"]
    targets = client.get("/v1/console", headers=headers).json()["targets"]
    assert {target["id"] for target in targets} == {"boostmybiz", project["id"]}
    assert len(client.get("/v1/console/projects", headers=headers).json()) == 2
    mission = client.post("/v1/console", headers=headers, json={
        "title": "Ricky Club", "brief": "Contrôler le site et le dépôt.",
        "agents": ["codex", "qwen-coder"], "max_calls": 2, "seconds": 300,
        "request_key": "ricky-1", "target": project["id"],
    })
    assert mission.status_code == 200
    mid = mission.json()["id"]
    assert client.get("/v1/console", headers=headers).json()["missions"][0]["target"] == project["id"]
    assert len(client.get("/v1/console?target=" + project["id"], headers=headers).json()["missions"]) == 1
    assert client.get("/v1/console?target=boostmybiz", headers=headers).json()["missions"] == []
    detail = client.get(f"/v1/console/{mid}", headers=headers).json()
    assert detail["target"] == project["id"]
    assert detail["agents"] == ["codex", "qwen-coder"]


@pytest.mark.parametrize("repository,website", [
    ("https://evil.test/x", "https://example.com"),
    ("owner/repo;touch /tmp/evil", "https://example.com"),
    ("owner/repo", "http://example.com"),
    ("owner/repo", "https://127.0.0.1/"),
    ("owner/repo", "https://localhost/"),
    ("owner/repo", "https://example.com:8443/"),
    ("owner/repo", "https://example.com@127.0.0.1/"),
    ("owner/repo", "https://example.com/?token=secret"),
])
def test_reject_unsafe_project_inputs(tmp_path, repository, website):
    missions = Missions(Store(tmp_path / "db.sqlite"))
    with pytest.raises(ValueError):
        missions.create_project("Bad", repository, website, "")


def test_custom_project_is_snapshotted_for_inspection(tmp_path):
    seen = []
    def collector(target, _capture_dir):
        seen.append(target)
        return {"repository": target["repository"], "website": target["website"], "browser": []}
    missions = Missions(Store(tmp_path / "db.sqlite"), collector=collector)
    project = missions.create_project("Ricky", "Jeffchoux/ricky-club", "https://ricky.example", "Contexte")
    mid = missions.create("Audit", "Vérifier le vrai site.", ["codex"], 1, 300, "custom", project["id"])
    missions.action(mid, "start")
    assert missions.prepare_next()
    assert seen[0]["repository"] == "Jeffchoux/ricky-club"
    assert seen[0]["notes"] == "Contexte"
    assert missions.detail(mid)["evidence"]["website"] == "https://ricky.example/"


def test_private_dns_never_reaches_browser(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kw: [
        (2, 1, 6, "", ("8.8.8.8", 443)), (2, 1, 6, "", ("127.0.0.1", 443)),
    ])
    with pytest.raises(ValueError, match="Adresse publique"):
        inspection._public_address("private.example")


def test_custom_repository_uses_default_branch_and_safe_sample(monkeypatch):
    seen = []
    def github(path):
        seen.append(path)
        if path == "repos/Jeffchoux/ricky-club":
            return {"default_branch": "trunk"}
        if path.endswith("/commits/trunk"):
            return {"sha": "a" * 40}
        if "/git/trees/" in path:
            return {"tree": [
                {"path": "README.md", "type": "blob", "sha": "b" * 40, "size": 15},
                {"path": "src/app.ts", "type": "blob", "sha": "c" * 40, "size": 15},
                {"path": ".env", "type": "blob", "sha": "d" * 40, "size": 15},
            ]}
        if "/git/blobs/" in path:
            return {"encoding": "base64", "content": base64.b64encode(b"Source code").decode()}
        return {"check_runs": []}
    monkeypatch.setattr(inspection, "_github_json", github)
    evidence = inspection._repository({"repository": "Jeffchoux/ricky-club", "custom": True})
    assert evidence["branch"] == "trunk"
    assert {item["path"] for item in evidence["files"]} == {"README.md", "src/app.ts"}
    assert not any("/git/blobs/" + "d" * 40 in path for path in seen)


def test_sample_keeps_code_and_tests_when_many_readmes_exist():
    files = {f"docs/{n}/README.md": {"size": 20} for n in range(20)}
    files.update({"src/page.ts": {"size": 20}, "tests/test_page.py": {"size": 20}})
    sample = inspection._sample_paths(files)
    assert len(sample) <= 10
    assert "src/page.ts" in sample
    assert "tests/test_page.py" in sample
