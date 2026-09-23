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
    for path in ("/", "/i18n.js", "/messages.js", "/landing.js", "/landing.css", "/decisions.js", "/decisions.css"):
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
def browser_server(tmp_path, monkeypatch, request):
    if os.environ.get("AGORA_BROWSER_TESTS") != "1":
        pytest.skip("Opt-in: AGORA_BROWSER_TESTS=1; install Playwright Chromium first")
    key = tmp_path / "operator.key"
    key.write_text("browser-fixture-not-a-real-credential")
    profiles = tmp_path / "agents.json"
    names = getattr(request, "param", ["local"])
    profiles.write_text(json.dumps({name: {"label": "Fixture " + name + " agent", "provider": "ollama", "model": "fixture-only"} for name in names}))
    profiles.chmod(0o600)
    env = dict(os.environ, AGORA_ADMIN_TOKEN_FILE=str(key), AGORA_AGENTS_FILE=str(profiles), AGORA_DB=str(tmp_path / "db"))
    env.pop("AGORA_LEGACY_INSTALLATION", None)
    env.pop("AGORA_LAYA_TOKEN_FILE", None)
    if request.node.get_closest_marker("laya_live"):
        live_token = os.environ.get("AGORA_TEST_LAYA_TOKEN_FILE")
        if not live_token:
            pytest.skip("Opt-in: AGORA_TEST_LAYA_TOKEN_FILE and a real running Mac helper")
        env["AGORA_LAYA_TOKEN_FILE"] = live_token
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
                if step == 4:
                    board = page.locator("#demo-decision")
                    expect(board).to_contain_text("Fictional example · no model calls")
                    expect(board.locator(".decision-positions > li")).to_have_count(2)
                    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                    board.locator("summary").click()
                    with page.expect_download() as download:
                        board.get_by_role("button", name="Download decision brief (.txt)").click()
                    report = Path(download.value.path()).read_text()
                    assert "Fictional example · no model calls" in report
                    assert "Agreement does not establish truth" in report
                    if scenario == "repo":
                        artifacts = Path(os.environ.get("AGORA_BROWSER_ARTIFACTS", str(tmp_path)))
                        artifacts.mkdir(parents=True, exist_ok=True)
                        board.screenshot(path=str(artifacts / f"decision-example-{width}.png"))
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
        page.locator("#decision-question").fill("Should we launch this pilot?")
        page.locator('[name="agent"]').check()
        page.locator("#chat-body").fill("Une idée à conserver, not UI copy.")
        page.locator("#language").select_option("fr")
        expect(page.locator("#new-project")).to_have_text("Ajouter un projet")
        expect(page.locator("#title")).to_have_value("Keep my title")
        expect(page.locator("#brief")).to_have_value("Do not translate or erase my own brief.")
        expect(page.locator("#decision-question")).to_have_value("Should we launch this pilot?")
        expect(page.locator("#chat-body")).to_have_value("Une idée à conserver, not UI copy.")
        expect(page.locator('[name="agent"]')).to_be_checked()
        page.locator("#language").select_option("en")
        page.locator("#create").click()
        expect(page.locator("#detail")).to_be_visible()
        expect(page.locator("#detail")).to_contain_text("Queued")
        expect(page.locator("#detail")).to_contain_text("Keep my title")
        expect(page.locator("#detail .decision-room")).to_contain_text("Should we launch this pilot?")
        expect(page.locator("#detail .decision-room")).to_contain_text("0 of 1 selected agents")
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


@pytest.mark.parametrize("width", [320, 768, 1024, 1440])
def test_laya_suggestion_requires_explicit_acceptance(browser_server, width, tmp_path):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": 1000}, reduced_motion="reduce")
        errors, mutations, suggestions = [], [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: mutations.append(request.url) if request.method == "POST" else None)

        def overview(route):
            response = route.fetch()
            data = response.json()
            data["laya"] = {"configured": True}
            route.fulfill(response=response, json=data)

        def suggest(route):
            suggestions.append(route.request.post_data_json)
            route.fulfill(json={"category": "ux", "engine": "laya-coreml", "experimental": True})

        page.route(re.compile(r"/v1/console(?:\?.*)?$"), overview)
        page.route("**/v1/console/laya/suggestions", suggest)
        page.goto(browser_server)
        expect(page.locator("#laya-assist")).to_be_hidden()
        page.locator("#show-login").click()
        page.locator("#token").fill("browser-fixture-not-a-real-credential")
        page.locator("#login-form button").click()
        expect(page.locator("#workspace")).to_be_visible()
        page.locator("#new-project").click()
        page.locator("#project-label").fill("Laya fixture project")
        page.locator("#save-project").click()
        expect(page.locator("#notice")).to_contain_text("Project saved")
        brief = "Review the keyboard navigation and contrast of our mobile checkout."
        page.locator("#brief").fill(brief)
        mutations.clear()
        page.locator("#laya-suggest").focus()
        page.keyboard.press("Enter")
        expect(page.locator("#laya-result")).to_contain_text("Suggested focus: UX and accessibility")
        expect(page.locator("#brief")).to_have_value(brief)
        expect(page.locator('[name="agent"]')).not_to_be_checked()
        assert suggestions == [{"brief": brief}]
        assert mutations == [browser_server + "/v1/console/laya/suggestions"]
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        artifacts = Path(os.environ.get("AGORA_BROWSER_ARTIFACTS", str(tmp_path)))
        artifacts.mkdir(parents=True, exist_ok=True)
        page.locator("#mission-form").screenshot(path=str(artifacts / f"laya-focus-{width}.png"))
        page.locator("#language").select_option("fr")
        expect(page.locator("#laya-result")).to_contain_text("Angle suggéré : UX et accessibilité")
        page.get_by_role("button", name="Ajouter cet angle à ma question").click()
        expect(page.locator("#brief")).to_have_value(re.compile(re.escape(brief) + r"\n\nAngle de revue"))
        assert "Prioriser l’utilisabilité" in page.locator("#brief").input_value()
        expect(page.locator("#laya-result")).to_contain_text("Angle ajouté")
        page.locator("#language").select_option("en")
        # No calls for invalid length; changing input invalidates an earlier result.
        page.locator("#brief").fill("x" * 1201)
        expect(page.locator("#laya-result")).to_be_empty()
        page.locator("#laya-suggest").click()
        expect(page.locator("#laya-result")).to_contain_text("has not been shortened or sent")
        assert len(suggestions) == 1
        page.locator("#brief").fill(brief)
        page.unroute("**/v1/console/laya/suggestions", suggest)
        page.route("**/v1/console/laya/suggestions", lambda route: route.fulfill(status=503, json={"error":"unavailable"}))
        page.locator("#laya-suggest").click()
        expect(page.locator("#laya-result")).to_contain_text("You can continue without Laya")
        expect(page.locator("#create")).to_be_enabled()
        assert not errors, errors
        browser.close()


def test_laya_discards_stale_and_logged_out_results(browser_server):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def overview(route):
            response = route.fetch()
            data = response.json()
            data["laya"] = {"configured": True}
            route.fulfill(response=response, json=data)

        page.route(re.compile(r"/v1/console(?:\?.*)?$"), overview)
        pending = []
        page.route("**/v1/console/laya/suggestions", lambda route: pending.append(route))
        page.goto(browser_server)
        page.locator("#show-login").click()
        page.locator("#token").fill("browser-fixture-not-a-real-credential")
        page.locator("#login-form button").click()
        expect(page.locator("#workspace")).to_be_visible()
        for name in ("First Laya project", "Second Laya project"):
            page.locator("#new-project").click()
            page.locator("#project-label").fill(name)
            page.locator("#save-project").click()
            expect(page.locator("#target option:checked")).to_have_text(name)
        for mutation in ("input", "project", "logout"):
            page.locator("#brief").fill("Review keyboard navigation on this website.")
            with page.expect_request("**/v1/console/laya/suggestions"):
                page.locator("#laya-suggest").click()
            expect(page.locator("#laya-result")).to_contain_text("Laya is reading")
            if mutation == "input":
                page.locator("#brief").fill("Find errors in this Python module instead.")
            elif mutation == "project":
                page.locator("#target").select_option(label="First Laya project")
            else:
                page.locator("#logout").click()
            pending.pop().fulfill(json={"category":"ux", "engine":"laya-coreml", "experimental":True})
            page.wait_for_load_state("networkidle")
            expect(page.locator("#laya-result")).to_be_empty()
        expect(page.locator("#workspace")).to_be_hidden()
        expect(page.locator("#laya-assist")).to_be_hidden()
        browser.close()


@pytest.mark.laya_live
def test_real_laya_helper_from_browser(browser_server, tmp_path):
    """Explicit opt-in only; real local model, fake console credential, no runner."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors, posts = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: posts.append(request.url) if request.method == "POST" else None)
        page.goto(browser_server)
        page.locator("#show-login").click()
        page.locator("#token").fill("browser-fixture-not-a-real-credential")
        page.locator("#login-form button").click()
        expect(page.locator("#workspace")).to_be_visible()
        for brief, category in (
            ("Find programming errors in this Python module and review its automated tests.", "Code and tests"),
            ("Define the target customers and value proposition for a new product.", "Product and positioning"),
            ("Review mobile checkout usability, keyboard navigation and color contrast.", "UX and accessibility"),
        ):
            page.locator("#brief").fill(brief)
            page.locator("#laya-suggest").click()
            expect(page.locator("#laya-result")).to_contain_text("Suggested focus: " + category, timeout=20000)
            expect(page.locator("#brief")).to_have_value(brief)
        page.get_by_role("button", name="Add this focus to my question").click()
        expect(page.locator("#brief")).to_have_value(re.compile("accepted by the operator"))
        expect(page.locator('[name="agent"]')).not_to_be_checked()
        artifacts = Path(os.environ.get("AGORA_BROWSER_ARTIFACTS", str(tmp_path)))
        artifacts.mkdir(parents=True, exist_ok=True)
        page.locator("#mission-form").screenshot(path=str(artifacts / "laya-real-accepted.png"))
        assert posts == [browser_server + "/v1/console/laya/suggestions"] * 3
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("browser_server", [["local", "second"]], indirect=True)
def test_decision_snapshot_export_and_failed_latest(browser_server, tmp_path, monkeypatch):
    from playwright.sync_api import expect, sync_playwright

    from agora.missions import Missions
    from agora.store import Store
    from agora.worker import Contribution

    monkeypatch.delenv("AGORA_LEGACY_INSTALLATION", raising=False)
    monkeypatch.setenv("AGORA_AGENTS_FILE", str(tmp_path / "agents.json"))
    missions = Missions(Store(tmp_path / "db"))
    mid = missions.create("Decision browser fixture", "PRIVATE_BRIEF_SENTINEL", ["local", "second"],
                          4, 600, "snapshot", decision_question="Should we ship <img src=x onerror=alert(1)>?")
    missions.action(mid, "start")
    for verdict in ("proceed", "revise"):
        turn = missions.reserve()
        missions.finish(turn["turn"], Contribution(kind=turn["expected_kind"], body="PRIVATE_BODY_SENTINEL", assessment={
            "verdict": verdict, "rationale": "<script>window.injected=true</script>",
            "next_check": "Observe the missing journey.", "references": []}))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 320, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(browser_server)
        page.locator("#show-login").click()
        page.locator("#token").fill("browser-fixture-not-a-real-credential")
        page.locator("#login-form button").click()
        page.locator("#mission-list button").first.click()
        board = page.locator("#detail .decision-room")
        expect(board).to_contain_text("Positions differ")
        expect(board).to_contain_text("Provisional · 2 of 2")
        expect(board.locator("img, script")).to_have_count(0)
        assert page.evaluate("window.injected") is None
        board.locator("summary").click()
        expect(board.locator(".decision-report")).to_be_visible()
        with page.expect_download() as download:
            board.get_by_role("button", name="Download decision brief (.txt)").click()
        report = Path(download.value.path()).read_text()
        assert mid in report and "Decision browser fixture" in report
        assert "PRIVATE_BRIEF_SENTINEL" not in report and "PRIVATE_BODY_SENTINEL" not in report
        assert "<script>window.injected=true</script>" in report
        assert download.value.suggested_filename.endswith(".txt")
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        board.locator(".decision-read").first.click()
        expect(page.locator("#conversation-transcript")).to_have_attribute("open", "")
        # Latest failure hides the older positive assessment, without inventing a vote.
        missions.finish(missions.reserve()["turn"])
        page.locator("#language").select_option("fr")
        expect(board).to_contain_text("Dernier appel échoué")
        expect(board).to_contain_text("Provisoire · 1 agents choisis sur 2")
        expect(board.locator(".decision-verdict").first).to_have_text("Dernier appel échoué")
        expect(board.locator(".decision-report")).to_be_visible()
        assert not errors, errors
        browser.close()
