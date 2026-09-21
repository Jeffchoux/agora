"""Run browser checks with AGORA_BROWSER_TESTS=1; no model runner is started."""
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from agora.server import create_app


def test_public_example_does_not_expose_operator_data(tmp_path, monkeypatch):
    monkeypatch.delenv("AGORA_LEGACY_INSTALLATION", raising=False)
    client = TestClient(create_app(tmp_path / "db"))
    for path in ("/", "/i18n.js", "/messages.js", "/landing.js", "/landing.css"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
    assert '<html lang="en">' in client.get("/").text
    assert "fictional scenario" in client.get("/").text
    assert "script-src 'self'" in client.get("/").headers["content-security-policy"]
    for path in ("/v1/console", "/v1/console/projects", "/operator.key", "/credentials.json", "/static/../operator.key"):
        assert client.get(path).status_code == 401
    assert client.post("/v1/console", json={}).status_code == 401


@pytest.fixture
def browser_server(tmp_path, monkeypatch):
    if os.environ.get("AGORA_BROWSER_TESTS") != "1":
        pytest.skip("Opt-in: AGORA_BROWSER_TESTS=1; install Playwright Chromium first")
    key = tmp_path / "operator.key"
    key.write_text("browser-fixture-not-a-real-credential")
    profiles = tmp_path / "agents.json"
    profiles.write_text(json.dumps({"local": {"label": "Fixture local agent", "provider": "ollama", "model": "fixture-only"}}))
    profiles.chmod(0o600)
    env = dict(os.environ, AGORA_ADMIN_TOKEN_FILE=str(key), AGORA_AGENTS_FILE=str(profiles), AGORA_DB=str(tmp_path / "db"))
    env.pop("AGORA_LEGACY_INSTALLATION", None)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "agora.server:create_app", "--factory", "--host", "127.0.0.1", "--port", str(port)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                if httpx.get(url + "/health").status_code == 200:
                    break
            except httpx.ConnectError:
                pass
            time.sleep(.05)
        else:
            pytest.fail("Local fixture server failed to start")
        yield url
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.mark.parametrize("width", [320, 768, 1024, 1440])
def test_international_first_visit_and_workspace(browser_server, width, tmp_path):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": 1000}, locale="fr-FR", reduced_motion="reduce")
        errors, requests = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: requests.append((request.method, request.url)))
        page.goto(browser_server)
        expect(page.locator("html")).to_have_attribute("lang", "en")
        expect(page.locator("#welcome")).to_be_visible()
        expect(page.locator("#login")).to_be_hidden()
        for scenario in ("repo", "site", "idea"):
            page.locator(f'[data-scenario="{scenario}"]').click()
            for step in range(1, 5):
                expect(page.locator("#demo-progress")).to_have_text(f"{step} / 4")
                assert page.locator("#demo-body").inner_text()
                page.locator("#demo-next").click()
        assert not any("/v1/" in url for _, url in requests), requests
        page.locator("#language").select_option("fr")
        expect(page.locator("html")).to_have_attribute("lang", "fr")
        expect(page.locator("#demo-heading")).to_have_text("Que voulez-vous examiner ?")
        page.reload()
        expect(page.locator("html")).to_have_attribute("lang", "fr")
        page.locator("#language").select_option("en")
        page.locator("#explore-example").click()
        expect(page.locator("#example")).to_be_focused()
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        artifacts = Path(os.environ.get("AGORA_BROWSER_ARTIFACTS", str(tmp_path)))
        artifacts.mkdir(parents=True, exist_ok=True)
        page.locator("#show-welcome").click()
        page.screenshot(path=str(artifacts / f"landing-{width}.png"), full_page=True)
        page.locator("#show-login").click()
        page.locator("#token").fill("browser-fixture-not-a-real-credential")
        page.locator("#login-form button").click()
        expect(page.locator("#workspace")).to_be_visible()
        page.locator("#new-project").click()
        page.locator("#project-label").fill("My independent project")
        page.locator("#save-project").click()
        expect(page.locator("#notice")).to_contain_text("Project saved")
        page.locator("#title").fill("Keep my title")
        page.locator("#brief").fill("Do not translate or erase my own brief.")
        page.locator('[name="agent"]').check()
        page.locator("#chat-body").fill("Une idée à conserver, not UI copy.")
        page.locator("#language").select_option("fr")
        expect(page.locator("#new-project")).to_have_text("Ajouter un projet")
        expect(page.locator("#title")).to_have_value("Keep my title")
        expect(page.locator("#brief")).to_have_value("Do not translate or erase my own brief.")
        expect(page.locator("#chat-body")).to_have_value("Une idée à conserver, not UI copy.")
        expect(page.locator('[name="agent"]')).to_be_checked()
        page.locator("#language").select_option("en")
        page.locator("#create").click()
        expect(page.locator("#detail")).to_be_visible()
        expect(page.locator("#detail")).to_contain_text("Queued")
        expect(page.locator("#detail")).to_contain_text("Keep my title")
        page.locator("#show-welcome").click()
        expect(page.locator("#welcome")).to_be_visible()
        page.locator("#language").select_option("fr")
        expect(page.locator("#welcome")).to_be_visible()
        page.locator("#back-workspace").click()
        expect(page.locator("#workspace")).to_be_visible()
        page.locator("#language").select_option("en")
        expect(page.locator("#detail")).to_contain_text("Queued")
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        # A completed network response must not re-open a signed-out workspace.
        pending = []

        def delay_overview(route):
            pending.append((route, route.fetch()))

        page.route(re.compile(r"/v1/console(?:\?.*)?$"), delay_overview)
        with page.expect_request(lambda request: "/v1/console" in request.url):
            page.locator("#language").select_option("fr")
        page.wait_for_function("document.documentElement.lang === 'fr'")
        page.locator("#logout").click()
        assert pending
        for route, response in pending:
            route.fulfill(response=response)
        page.wait_for_load_state("networkidle")
        expect(page.locator("#workspace")).to_be_hidden()
        expect(page.locator("#welcome")).to_be_visible()
        expect(page.locator("#mission-list")).to_be_empty()
        expect(page.locator("#detail")).to_be_empty()
        assert not errors, errors
        assert not any(not url.startswith(browser_server) for _, url in requests), requests
        browser.close()
