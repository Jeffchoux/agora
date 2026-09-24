import json
import os
import subprocess
import sys

import pytest

from agora.import_profiles import ImportError, import_agents


def profile(**values):
    return {"label": "My agent", "provider": "ollama", "model": "local-model", **values}


@pytest.fixture
def files(tmp_path):
    directory = tmp_path / "installation"
    directory.mkdir(mode=0o700)
    target = directory / "agents.json"
    target.write_text(json.dumps({"existing": profile()}))
    target.chmod(0o600)
    source = tmp_path / "download.json"
    source.write_text(json.dumps({"new": profile()}))
    source.chmod(0o644)
    return directory, target, source


def test_merge_preserves_existing_and_never_opens_credentials(files):
    directory, target, source = files
    original = json.loads(target.read_text())
    source.write_text(json.dumps({"new": profile(provider="anthropic", model="claude-model", operator_authorized=False,
                                                key_env="ANTHROPIC_API_KEY", credential_file="~/.config/agora/credentials.json")}))
    assert import_agents(source, directory, True) == 1
    result = json.loads(target.read_text())
    assert result["existing"] == original["existing"]
    assert result["new"]["operator_authorized"] is True
    assert result["new"]["credential_file"] == str(directory / "credentials.json")
    assert target.stat().st_mode & 0o777 == 0o600
    assert sorted(p.name for p in directory.iterdir()) == ["agents.json"]


@pytest.mark.parametrize("authorized", [False, True])
def test_export_cannot_authorize_external(files, authorized):
    directory, target, source = files
    before = target.read_bytes()
    source.write_text(json.dumps({"new": profile(provider="claude-cli", operator_authorized=authorized)}))
    with pytest.raises(ImportError, match="--authorize-external"):
        import_agents(source, directory)
    assert target.read_bytes() == before


@pytest.mark.parametrize("data", [
    {}, [], {"existing": profile(), "new": profile()},
    {str(i): profile() for i in range(33)},
    {"new": profile(model="")}, {"new": profile(model="   ")},
    {"new": profile(api_key="sk-secret-do-not-print")},
    {"new": profile(key_env="sk-secret-do-not-print")},
    {"new": profile(credential_file="sk-secret-do-not-print")},
    {"new": profile(credential_file={"key": "sk-secret-do-not-print"})},
    {"new": profile(endpoint="https://user:secret@example.com")},
    {"new": profile(endpoint="https://example.com?key=secret")},
    {"new": profile(max_tokens=30)},
    {"new": profile(provider="unknown")},
    {"new": profile(provider="claude-cli", operator_authorized="yes")},
    {"invalid id": profile()}, {"new": "invalid"},
])
def test_invalid_import_is_all_or_nothing(files, data):
    directory, target, source = files
    before = target.read_bytes()
    source.write_text(json.dumps(data))
    with pytest.raises(ImportError) as error:
        import_agents(source, directory, True)
    assert "sk-secret-do-not-print" not in str(error.value)
    assert target.read_bytes() == before
    assert sorted(p.name for p in directory.iterdir()) == ["agents.json"]


@pytest.mark.parametrize("content", ["{", '{"new": {}, "new": {}}', "x" * 65537])
def test_malformed_and_oversized_source(files, content):
    directory, target, source = files
    before = target.read_bytes()
    source.write_text(content)
    with pytest.raises(ImportError):
        import_agents(source, directory)
    assert target.read_bytes() == before


@pytest.mark.parametrize("unsafe", ["target-mode", "directory-mode", "target-symlink", "directory-symlink", "target-hardlink", "source-symlink"])
def test_unsafe_paths_refused(files, unsafe):
    directory, target, source = files
    before = target.read_bytes()
    if unsafe == "target-mode":
        target.chmod(0o644)
    elif unsafe == "directory-mode":
        directory.chmod(0o755)
    elif unsafe == "target-symlink":
        moved = directory / "original"
        target.rename(moved)
        target.symlink_to(moved)
    elif unsafe == "directory-symlink":
        alias = directory.parent / "alias"
        alias.symlink_to(directory, target_is_directory=True)
        directory = alias
    elif unsafe == "target-hardlink":
        os.link(target, directory / "other")
    else:
        alias = directory.parent / "source-alias"
        alias.symlink_to(source)
        source = alias
    with pytest.raises(ImportError):
        import_agents(source, directory)
    assert target.read_bytes() == before


def test_total_profile_limit(files):
    directory, target, source = files
    target.write_text(json.dumps({str(i): profile() for i in range(32)}))
    before = target.read_bytes()
    with pytest.raises(ImportError):
        import_agents(source, directory)
    assert target.read_bytes() == before


def test_foreign_ownership_refused(files, monkeypatch):
    directory, target, source = files
    before = target.read_bytes()
    owner = os.getuid()
    monkeypatch.setattr(os, "getuid", lambda: owner + 1)
    with pytest.raises(ImportError):
        import_agents(source, directory)
    assert target.read_bytes() == before


def test_concurrent_edit_is_not_overwritten(files, monkeypatch):
    directory, target, source = files
    real_fsync = os.fsync
    replacement = json.dumps({"edited": profile()})

    def concurrent_edit(fd):
        target.write_text(replacement)
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", concurrent_edit)
    with pytest.raises(ImportError, match="changed during import"):
        import_agents(source, directory)
    assert target.read_text() == replacement
    assert sorted(p.name for p in directory.iterdir()) == ["agents.json"]


def test_cli_does_not_disclose_invalid_input(files):
    directory, _target, source = files
    source.write_text('{"new": {"api_key": "sk-secret-do-not-print"}}')
    result = subprocess.run([sys.executable, "-m", "agora", "import-agents", str(source), "--directory", str(directory)], capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert "sk-secret-do-not-print" not in result.stdout + result.stderr


def test_cli_import(files):
    directory, target, source = files
    result = subprocess.run([sys.executable, "-m", "agora", "import-agents", str(source), "--directory", str(directory)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "Imported 1" in result.stdout
    assert set(json.loads(target.read_text())) == {"existing", "new"}
