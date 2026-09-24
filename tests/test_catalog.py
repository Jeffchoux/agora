"""Public catalogue tests. Browser opt-in uses an isolated local fixture, no runner."""
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_global_ui import browser_server as global_browser_server

from agora.config import validate_profiles
from agora.import_profiles import import_agents
from agora.server import create_app

browser_server = global_browser_server


def test_catalogue_is_public_and_not_a_secret_inventory(tmp_path):
    with TestClient(create_app(tmp_path / "db")) as client:
        for path in ("/catalog.js", "/catalog.css", "/providers.json"):
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
        entries = client.get("/providers.json").json()["entries"]
        assert len(entries) >= 25
        assert len({p["id"] for p in entries}) == len(entries)
        assert {"anthropic-api", "openai-api", "mistral-api", "gemini-api", "ollama-local"} <= {p["id"] for p in entries}
        for p in entries:
            assert p["docs"].startswith("https://")
            assert p["note"]["en"] and p["note"]["fr"]
            assert "api_key" not in p and "credential_file" not in p
            if p["mode"] == "pending":
                assert "provider" not in p
                continue
            profile = {"label": p["name"], "model": "fixture-model", "provider": p["provider"], "operator_authorized": True}
            if p.get("endpoint"):
                profile["endpoint"] = p["endpoint"]
            if p.get("custom_endpoint"):
                profile["endpoint"] = "https://example.com/v1"
            validate_profiles({p["id"]: profile})
        assert client.get("/v1/console").status_code == 401
        assert client.post("/v1/console", json={}).status_code == 401


@pytest.mark.parametrize("width", [320, 768, 1024, 1440])
def test_catalog_search_select_export_import(browser_server, width, tmp_path):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": 1000}, reduced_motion="reduce")
        errors, requests = [], []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("request", lambda r: requests.append((r.method, r.url)))
        page.goto(browser_server)
        opener = page.locator(".header-actions [data-open-catalog]")
        opener.click()
        expect(page.locator("#catalog-list .catalog-row")).to_have_count(31)
        expect(page.locator("#provider-gemini-cli")).to_be_disabled()
        page.locator("#catalog-search").fill("does-not-exist")
        expect(page.locator("#catalog-list")).to_contain_text("No match")
        page.locator("#catalog-search").fill("Claude")
        page.locator("#provider-anthropic-api").check()
        page.locator("#models-anthropic-api").fill("fixture-model-a\nfixture-model-b")
        page.locator("#catalog-search").fill("Ollama")
        page.locator("#provider-ollama-local").check()
        page.locator("#models-ollama-local").fill("fixture-local")
        page.locator("#catalog-search").fill("")
        expect(page.locator("#models-anthropic-api")).to_have_value("fixture-model-a\nfixture-model-b")
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        assert not page.locator("#model-catalog").evaluate("el => el.scrollWidth > el.clientWidth")
        artifacts = Path(os.environ.get("AGORA_BROWSER_ARTIFACTS", str(tmp_path)))
        artifacts.mkdir(parents=True, exist_ok=True)
        page.locator('#catalog-title').scroll_into_view_if_needed()
        page.screenshot(path=str(artifacts / f"catalog-{width}.png"))
        page.locator('#catalog-review').click()
        expect(page.locator('#catalog-list .catalog-row')).to_have_count(2)
        with page.expect_download() as result:
            page.locator("#catalog-download").click()
        source = Path(result.value.path())
        exported = json.loads(source.read_text())
        assert len(exported) == 3
        assert exported["anthropic-api-1"]["operator_authorized"] is False
        assert "operator_authorized" not in exported["ollama-local-1"]
        directory = tmp_path.resolve() / "installation"
        directory.mkdir(mode=0o700)
        target = directory / "agents.json"
        target.write_text("{}")
        target.chmod(0o600)
        assert import_agents(source, directory, True) == 3
        assert json.loads(target.read_text())["anthropic-api-2"]["model"] == "fixture-model-b"
        page.keyboard.press("Escape")
        expect(page.locator("#model-catalog")).not_to_be_visible()
        expect(opener).to_be_focused()
        page.locator("#language").select_option("fr")
        opener.click()
        expect(page.locator("#catalog-title")).to_have_text("Choisissez vos modèles")
        expect(page.locator("#models-anthropic-api")).to_have_value("fixture-model-a\nfixture-model-b")
        page.locator("#catalog-filter").select_option("pending")
        expect(page.locator("#catalog-list input[type=checkbox]:enabled")).to_have_count(0)
        assert not errors
        assert not any(method != "GET" or not url.startswith(browser_server) for method, url in requests)
        assert not any("/v1/" in url for _, url in requests)
        browser.close()


def test_catalog_loading_failure_retry(browser_server):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.route("**/providers.json", lambda route: route.fulfill(status=503, body="unavailable"))
        page.goto(browser_server)
        page.get_by_role("button", name="Models & connections").click()
        expect(page.locator("#catalog-status")).to_contain_text("Directory unavailable")
        expect(page.locator("#catalog-download")).to_be_disabled()
        page.unroute("**/providers.json")
        page.locator("#catalog-retry").click()
        expect(page.locator("#catalog-list .catalog-row")).to_have_count(31)
        browser.close()
