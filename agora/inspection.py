"""Bounded, read-only evidence for explicitly configured mission targets."""

import base64
import json
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

TARGETS = {
    "boostmybiz": {
        "label": "BoostMyBiz",
        "repository": "Jeffchoux/BoostMyBiz.pro",
        "website": "https://boostmybiz.pro/",
        "production_manifest": "/home/galaxia/.local/share/astra/deployments/boostmybiz.json",
        "files": (
            "AGENTS.md",
            "README.md",
            "STATE.md",
            "DESIGN.md",
            "engine/README.md",
            "engine/templates/site.html.j2",
            "engine/test/test_global_landing_locale.py",
        ),
    }
}
WIDTHS = (320, 768, 1440)


def _github_json(path):
    try:
        result = subprocess.run(
            ["gh", "api", path],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if len(result.stdout) > 2_000_000:
            raise ValueError("GitHub response too large")
        return json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise ValueError("Lecture GitHub indisponible") from exc


def _repository(target):
    repo = target["repository"]
    commit = _github_json(f"repos/{repo}/commits/main")
    sha = commit["sha"]
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("SHA GitHub invalide")
    tree = _github_json(f"repos/{repo}/git/trees/{sha}?recursive=1")
    if tree.get("truncated"):
        raise ValueError("Arbre GitHub tronqué")
    files = {item["path"]: item for item in tree["tree"] if item["type"] == "blob"}
    excerpts = []
    for path in target["files"]:
        item = files.get(path)
        if not item or item["size"] > 200_000:
            continue
        blob = _github_json(f"repos/{repo}/git/blobs/{item['sha']}")
        if blob.get("encoding") != "base64":
            continue
        raw = base64.b64decode(blob["content"], validate=False)
        body = raw.decode("utf-8", errors="replace")
        excerpt = "\n".join(
            f"{number}: {line}" for number, line in enumerate(body.splitlines(), 1)
        )[:1200]
        excerpts.append({"path": path, "blob_sha": item["sha"], "excerpt": excerpt})
    checks = _github_json(f"repos/{repo}/commits/{sha}/check-runs?per_page=50")
    return {
        "repository": repo,
        "github_sha": sha,
        "file_count": len(files),
        "files": excerpts,
        "checks": [
            {"name": run["name"], "status": run["status"], "conclusion": run["conclusion"]}
            for run in checks.get("check_runs", [])[:20]
        ],
    }


def _production(target):
    try:
        data = json.loads(Path(target["production_manifest"]).read_text())
        sha = data["source_sha"]
        if not isinstance(sha, str) or len(sha) != 40:
            return None
        return sha
    except (OSError, KeyError, ValueError):
        return None


def _browser(target, capture_dir):
    origin = urlparse(target["website"])
    results = []
    capture_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                context = browser.new_context(
                    viewport={"width": width, "height": 900},
                    service_workers="block",
                    accept_downloads=False,
                )
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error, sink=errors: sink.append(str(error)[:200]))

                def allow_known_origin(route):
                    request_url = urlparse(route.request.url)
                    if (
                        request_url.scheme == "https"
                        and request_url.hostname == origin.hostname
                        and route.request.method == "GET"
                    ):
                        route.continue_()
                    else:
                        route.abort()

                page.route("**/*", allow_known_origin)
                try:
                    response = page.goto(target["website"], wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_timeout(500)
                    state = page.evaluate("""() => ({
                      title: document.title.slice(0, 200),
                      lang: document.documentElement.lang,
                      h1: [...document.querySelectorAll('h1')].map(x => x.textContent.trim().slice(0, 160)).slice(0, 4),
                      main: !!document.querySelector('main'),
                      overflow: document.documentElement.scrollWidth > innerWidth,
                      images: document.images.length,
                      brokenImages: [...document.images].filter(x => x.complete && x.naturalWidth === 0).length,
                      missingAlt: [...document.images].filter(x => !x.hasAttribute('alt')).length,
                      actions: [...document.querySelectorAll('a,button')].filter(x => x.getClientRects().length).map(x => (x.textContent || x.getAttribute('aria-label') || '').trim().slice(0, 80)).filter(Boolean).slice(0, 12)
                    })""")
                    screenshot = capture_dir / f"{width}.png"
                    page.screenshot(path=str(screenshot), full_page=False, timeout=10000)
                    screenshot.chmod(0o600)
                    results.append({
                        "viewport": width,
                        "http_status": response.status if response else None,
                        "page_errors": errors[:5],
                        "screenshot": f"{width}.png",
                        **state,
                    })
                except (PlaywrightError, OSError) as exc:
                    results.append({"viewport": width, "error": type(exc).__name__})
                finally:
                    context.close()
        finally:
            browser.close()
    return results


def collect(target_id, capture_dir):
    """Collect immutable evidence; no repository code or model text is executed."""
    if target_id not in TARGETS:
        raise ValueError("Projet non connecté")
    target = TARGETS[target_id]
    repository = _repository(target)
    production_sha = _production(target)
    return {
        "target": target_id,
        "collected_at": int(time.time()),
        "website": target["website"],
        "production_sha": production_sha,
        "production_matches_github": production_sha == repository["github_sha"] if production_sha else None,
        **repository,
        "browser": _browser(target, Path(capture_dir)),
        "limitations": [
            "Échantillon de fichiers, pas revue exhaustive du dépôt.",
            "Contrôles navigateur publics et résultats CI ; aucun test du code du dépôt exécuté par Agora.",
            "Codex reçoit les captures ; les autres participants voient les mesures DOM.",
        ],
    }
