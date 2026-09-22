"""Public CLI contract: private setup, one local server, no provider calls."""

import contextlib
import fcntl
import json
import os
import select
import signal
import socket
import subprocess
import sys
import time

import httpx
import pytest


def cli(*args, **kwargs):
    return subprocess.run(
        [sys.executable, "-m", "agora", *args],
        text=True, capture_output=True, timeout=15, check=False, **kwargs,
    )


def test_start_missing_configuration_is_actionable_and_does_not_create_files(tmp_path):
    directory = tmp_path / "not-initialized"
    result = cli("start", "--directory", str(directory))
    assert result.returncode == 2
    assert "Run" in result.stderr and "agora init --directory" in result.stderr
    assert "Traceback" not in result.stderr
    assert not directory.exists()


def setup(directory):
    result = cli("init", "--directory", str(directory))
    assert result.returncode == 0, result.stderr
    return directory / "operator.key"


def test_start_rejects_insecure_key_without_disclosing_it(tmp_path):
    key = setup(tmp_path)
    key.chmod(0o644)
    result = cli("start", "--directory", str(tmp_path))
    assert result.returncode == 2
    assert "operator.key" in result.stderr and "0600" in result.stderr
    assert key.read_text().strip() not in result.stdout + result.stderr
    assert not (tmp_path / "agora.sqlite").exists()


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


@contextlib.contextmanager
def running(directory, env=None, port=None):
    port = port or free_port()
    process = subprocess.Popen(
        [sys.executable, "-m", "agora", "start", "--directory", str(directory), "--port", str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=1, trust_env=False) as client:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail(str(process.communicate()))
                try:
                    if client.get("/health").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.05)
            else:
                pytest.fail("Local server did not become ready")
            assert select.select([process.stdout], [], [], 5)[0], "Launcher did not report readiness"
            yield process, client
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            pytest.fail("Local launcher did not stop")


@pytest.mark.parametrize("stop_signal", [signal.SIGINT, signal.SIGTERM])
def test_one_command_serves_private_console_and_releases_runner_on_stop(tmp_path, stop_signal):
    key = setup(tmp_path)
    # Inherited settings from a different installation must not select its data/agents.
    env = dict(os.environ, AGORA_DB=str(tmp_path / "wrong.sqlite"), AGORA_LEGACY_INSTALLATION="1")
    with running(tmp_path, env) as (process, client):
        assert client.get("/").status_code == 200
        assert client.get("/v1/console").status_code == 401
        headers = {"Authorization": "Bearer " + key.read_text().strip()}
        board = client.get("/v1/console", headers=headers)
        assert board.status_code == 200
        assert board.json()["agents"] == []
        with (tmp_path / "agora.runner.lock").open("a") as lock, pytest.raises(BlockingIOError):
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        process.send_signal(stop_signal)
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stderr
        assert "Agora ready:" in stdout and "0 configured agent(s)" in stdout
        assert key.read_text().strip() not in stdout + stderr
    with (tmp_path / "agora.runner.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert not (tmp_path / "wrong.sqlite").exists()


def test_immediate_restart_on_same_port_after_keepalive_request(tmp_path):
    setup(tmp_path)
    port = free_port()
    for _ in range(2):
        with running(tmp_path, port=port) as (process, client):
            assert client.get("/health").status_code == 200
            process.terminate()
            process.wait(timeout=10)
            assert process.returncode == 0


@pytest.mark.parametrize("content", ["é" * 32, "a" * 32 + "\x00", "short"])
def test_unusable_operator_key_fails_before_serving(tmp_path, content):
    key = setup(tmp_path)
    key.write_text(content)
    result = cli("start", "--directory", str(tmp_path))
    assert result.returncode == 2
    assert "operator.key is unreadable or invalid" in result.stderr
    assert content not in result.stdout + result.stderr


def test_occupied_port_is_not_stopped_and_database_not_created(tmp_path):
    setup(tmp_path)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        result = cli("start", "--directory", str(tmp_path), "--port", str(listener.getsockname()[1]))
        assert result.returncode == 2
        assert "port is already in use" in result.stderr
        assert listener.fileno() >= 0
        assert not (tmp_path / "agora.sqlite").exists()


def test_existing_runner_is_never_replaced(tmp_path):
    setup(tmp_path)
    lock_path = tmp_path / "agora.runner.lock"
    lock_path.touch(mode=0o600)
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = cli("start", "--directory", str(tmp_path), "--port", str(free_port()))
        assert result.returncode == 2
        assert "runner already owns" in result.stderr
        assert not (tmp_path / "agora.sqlite").exists()


@pytest.mark.parametrize("content", ['{"secret-not-for-logs":', '[]', '{"private-value": {}}'])
def test_bad_profiles_are_actionable_without_echoing_content(tmp_path, content):
    setup(tmp_path)
    (tmp_path / "agents.json").write_text(content)
    result = cli("start", "--directory", str(tmp_path))
    assert result.returncode == 2
    assert "Invalid agents.json" in result.stderr
    assert content not in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("stop_signal", [None, signal.SIGINT, signal.SIGTERM])
def test_runner_completes_explicit_mission_with_fake_subscription_cli(tmp_path, monkeypatch, stop_signal):
    directory = tmp_path / "private"
    key = setup(directory)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_cli = fake_bin / "claude"
    marker = tmp_path / "fixture-called"
    fake_cli.write_text(
        f"#!{sys.executable}\nimport json, sys, time\nfrom pathlib import Path\n"
        "if 'auth' in sys.argv:\n"
        "    print(json.dumps({'loggedIn': True, 'authMethod': 'claude.ai'}))\n"
        "else:\n"
        f"    Path({str(marker)!r}).write_text('called')\n"
        "    time.sleep(1)\n"
        "    print(json.dumps({'structured_output': {'kind': "
        + repr("question" if stop_signal else "review")
        + ", 'body': 'Local fixture only.'}}))\n"
    )
    fake_cli.chmod(0o700)
    (directory / "agents.json").write_text(json.dumps({"fixture": {
        "label": "Test fixture", "provider": "claude-cli", "model": "fixture", "operator_authorized": True,
    }}))
    env = dict(os.environ, PATH=str(fake_bin) + os.pathsep + os.environ["PATH"])
    with running(directory, env) as (process, client):
        client.headers["Authorization"] = "Bearer " + key.read_text().strip()
        created = client.post("/v1/console", json={
            "title": "Local test", "brief": "Review this fictional description only.",
            "agents": ["fixture"], "max_calls": 2 if stop_signal else 1,
            "seconds": 300, "request_key": "launcher-test",
        })
        assert created.status_code == 200, created.text
        mid = created.json()["id"]
        assert client.post(f"/v1/console/{mid}/start", json={}).status_code == 200
        deadline = time.monotonic() + 10
        if stop_signal:
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.025)
            assert marker.exists(), "Fake provider was not started"
            process.send_signal(stop_signal)
            process.wait(timeout=10)
            assert process.returncode == 0
            # Reopen the public mission model without starting another runner.
            from agora.missions import Missions
            from agora.store import Store

            monkeypatch.setenv("AGORA_AGENTS_FILE", str(directory / "agents.json"))
            mission = Missions(Store(directory / "agora.sqlite")).detail(mid)
            assert mission["calls"] == 1  # a second authorized call must not start on shutdown
            assert mission["turns"][0]["body"] == "Local fixture only."
            return
        while time.monotonic() < deadline:
            mission = client.get(f"/v1/console/{mid}").json()
            if mission["status"] in {"finished", "failed"}:
                break
            time.sleep(0.1)
        assert mission["status"] == "finished", mission
        assert mission["calls"] == 1
        assert mission["turns"][0]["body"] == "Local fixture only."


def test_corrupt_database_has_safe_error(tmp_path):
    setup(tmp_path)
    database = tmp_path / "agora.sqlite"
    database.write_bytes(b"private-database-content-not-for-logs")
    database.chmod(0o600)
    result = cli("start", "--directory", str(tmp_path), "--port", str(free_port()))
    assert result.returncode == 2
    assert "Cannot open this installation" in result.stderr
    assert "Traceback" not in result.stderr and "private-database-content" not in result.stderr


def test_symlink_key_is_rejected_without_changing_target(tmp_path):
    directory = tmp_path / "private"
    key = setup(directory)
    outside = tmp_path / "original.key"
    key.rename(outside)
    key.symlink_to(outside)
    before = outside.read_bytes()
    result = cli("start", "--directory", str(directory))
    assert result.returncode == 2
    assert "regular private file" in result.stderr
    assert outside.read_bytes() == before


@pytest.mark.skipif(os.environ.get("AGORA_BROWSER_TESTS") != "1", reason="Opt-in Chromium check")
def test_combined_launcher_opens_a_real_browser_workspace(tmp_path):
    from playwright.sync_api import expect, sync_playwright

    key = setup(tmp_path)
    with running(tmp_path) as (_, client), sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 850})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(str(client.base_url))
            expect(page.locator("html")).to_have_attribute("lang", "en")
            page.locator("#show-login").click()
            page.locator("#keyfile").set_input_files(str(key))
            expect(page.locator("#workspace")).to_be_visible()
            expect(page.locator("#new-project")).to_be_enabled()
            assert errors == []
        finally:
            browser.close()
