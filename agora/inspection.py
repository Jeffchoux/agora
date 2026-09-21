"""Bounded, read-only evidence for explicitly configured mission targets."""

import base64
import ipaddress
import json
import re
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import quote, urlparse, urlsplit, urlunsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

TARGETS = {
    "boostmybiz": {
        "label": "BoostMyBiz",
        "repository": "Jeffchoux/BoostMyBiz.pro",
        "website": "https://boostmybiz.pro/",
        "public_link": {
            "label": "Describe my project",
            "host": "postpilot-rho-inky.vercel.app",
            "path": "/agence/demarrer",
        },
        "production_manifest": "/home/galaxia/.local/share/astra/deployments/boostmybiz.json",
        "files": (
            "AGENTS.md",
            "README.md",
            "STATE.md",
            "DESIGN.md",
            "engine/README.md",
            "engine/templates/site.html.j2",
            "engine/test/test_global_landing_locale.py",
            "app/[locale]/page.ts",
            "app/communication-messages.ts",
            "e2e/country-coverage.spec.ts",
        ),
    }
}
WIDTHS = (320, 768, 1440)
REPOSITORY = re.compile(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}\Z")
HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
SOURCE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".swift", ".html", ".css", ".vue", ".svelte")


def normalize_repository(raw):
    if not isinstance(raw, str) or len(raw) > 250:
        raise ValueError("Dépôt GitHub invalide")
    value = raw.strip()
    if value.startswith("https://github.com/"):
        value = value.removeprefix("https://github.com/").rstrip("/")
    value = value.removesuffix(".git")
    if not REPOSITORY.fullmatch(value) or ".." in value:
        raise ValueError("Indiquez un dépôt GitHub sous la forme owner/repo ou son URL")
    return value


def normalize_website(raw):
    if not isinstance(raw, str) or not 10 <= len(raw) <= 2048 or any(ord(c) < 32 for c in raw):
        raise ValueError("URL publique HTTPS invalide")
    try:
        url = urlsplit(raw.strip())
        host = (url.hostname or "").encode("idna").decode("ascii").lower()
        port = url.port
    except (ValueError, UnicodeError) as exc:
        raise ValueError("URL publique HTTPS invalide") from exc
    labels = host.split(".")
    if (
        url.scheme != "https" or url.username or url.password or url.query or url.fragment
        or port not in (None, 443) or len(labels) < 2
        or any(not HOST_LABEL.fullmatch(label) for label in labels)
    ):
        raise ValueError("Indiquez une URL publique HTTPS sans identifiant, paramètre ni port spécial")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("Les adresses IP directes ne sont pas acceptées")
    return urlunsplit(("https", host, url.path or "/", "", ""))


def _public_address(host):
    """Resolve every address; Chromium is pinned to one checked public IP."""
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise ValueError("Adresse publique introuvable") from exc
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("Adresse publique requise")
    return min(addresses, key=lambda address: (ipaddress.ip_address(address).version, address))


def _sample_paths(files):
    """Small cross-stack sample, excluding secrets, generated files and dependencies."""
    groups = {"context": [], "tests": [], "code": []}
    for path, item in files.items():
        lower = path.lower()
        parts = lower.split("/")
        if item.get("size", 0) > 200_000 or any(
            part in {"node_modules", "vendor", "dist", "build", ".next", "coverage", "credentials", "secrets"}
            or part.startswith(".env") or any(word in part for word in ("secret", "credential", "private_key", "token"))
            or part.endswith((".key", ".pem", ".lock", ".min.js"))
            for part in parts
        ):
            continue
        name = parts[-1]
        if name in {"readme.md", "agents.md", "design.md", "package.json", "pyproject.toml", "go.mod", "cargo.toml"}:
            group = "context"
        elif ("test" in parts or "tests" in parts or "e2e" in parts or name.startswith("test_") or name.endswith((".test.ts", ".spec.ts", ".test.tsx", ".spec.tsx"))) and name.endswith(SOURCE_SUFFIXES):
            group = "tests"
        elif name.endswith(SOURCE_SUFFIXES) and ("src" in parts or "app" in parts or len(parts) <= 2):
            group = "code"
        else:
            continue
        groups[group].append(path)
    for items in groups.values():
        items.sort(key=lambda path: (len(path.split("/")), path))
    chosen = groups["context"][:4] + groups["tests"][:3] + groups["code"][:3]
    for path in groups["context"] + groups["tests"] + groups["code"]:
        if len(chosen) >= 10:
            break
        if path not in chosen:
            chosen.append(path)
    return chosen


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


def _excerpt(path, body):
    lines = body.splitlines()
    if path == "app/[locale]/page.ts":
        selected = set()
        for index, line in enumerate(lines):
            if "const countryAgency" in line or "function applyCountryMode" in line:
                selected.update(range(max(0, index - 2), min(len(lines), index + 14)))
        if selected:
            return "\n".join(f"{i + 1}: {lines[i]}" for i in sorted(selected))[:2400]
    limit = 2400 if path == "e2e/country-coverage.spec.ts" else 1200
    return "\n".join(f"{number}: {line}" for number, line in enumerate(lines, 1))[:limit]


def _repository(target):
    repo = target["repository"]
    branch = "main"
    if target.get("custom"):
        metadata = _github_json(f"repos/{repo}")
        branch = metadata.get("default_branch")
        if not isinstance(branch, str) or not 1 <= len(branch) <= 100:
            raise ValueError("Branche GitHub par défaut introuvable")
    commit = _github_json(f"repos/{repo}/commits/{quote(branch, safe='')}")
    sha = commit["sha"]
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("SHA GitHub invalide")
    tree = _github_json(f"repos/{repo}/git/trees/{sha}?recursive=1")
    if tree.get("truncated"):
        raise ValueError("Arbre GitHub tronqué")
    files = {item["path"]: item for item in tree["tree"] if item["type"] == "blob"}
    excerpts = []
    for path in target.get("files") or _sample_paths(files):
        item = files.get(path)
        if not item or item["size"] > 200_000:
            continue
        blob = _github_json(f"repos/{repo}/git/blobs/{item['sha']}")
        if blob.get("encoding") != "base64":
            continue
        raw = base64.b64decode(blob["content"], validate=False)
        body = raw.decode("utf-8", errors="replace")
        excerpt = _excerpt(path, body)
        excerpts.append({"path": path, "blob_sha": item["sha"], "excerpt": excerpt})
    checks = _github_json(f"repos/{repo}/commits/{sha}/check-runs?per_page=50")
    return {
        "repository": repo,
        "branch": branch,
        "github_sha": sha,
        "file_count": len(files),
        "files": excerpts,
        "checks": [
            {"name": run["name"], "status": run["status"], "conclusion": run["conclusion"]}
            for run in checks.get("check_runs", [])[:20]
        ],
    }


def _production(target):
    if not target.get("production_manifest"):
        return None
    try:
        data = json.loads(Path(target["production_manifest"]).read_text())
        sha = data["source_sha"]
        if not isinstance(sha, str) or len(sha) != 40:
            return None
        return sha
    except (OSError, KeyError, ValueError):
        return None


def _approved_link(href, target):
    parsed = urlparse(href)
    link = target["public_link"]
    return parsed.scheme == "https" and parsed.netloc == link["host"] and parsed.path == link["path"]


def _public_link_probe(page, target):
    """Exercise a fixed, public fallback link without submitting a form."""
    label = target["public_link"]["label"]
    href = page.evaluate(
        """label => [...document.querySelectorAll('a')]
          .find(a => a.textContent.trim() === label && a.getClientRects().length)?.href || null""",
        label,
    )
    if not href:
        return {"label": label, "present": False}
    if not _approved_link(href, target):
        return {"label": label, "present": True, "destination_allowed": False}
    tab_steps = None
    page.evaluate("document.activeElement?.blur()")
    for step in range(1, 81):
        page.keyboard.press("Tab")
        if page.evaluate(
            "label => document.activeElement?.textContent.trim() === label", label
        ):
            tab_steps = step
            break
    enter_opened_expected = None
    if tab_steps is not None:
        try:
            with page.context.expect_page(timeout=5000) as new_page:
                page.keyboard.press("Enter")
            popup = new_page.value
            try:
                popup.wait_for_load_state("domcontentloaded", timeout=10000)
                enter_opened_expected = _approved_link(popup.url, target)
            finally:
                popup.close()
        except PlaywrightError:
            enter_opened_expected = False
    try:
        response = page.request.get(href, max_redirects=0, timeout=10000)
        destination_status = response.status
        destination_location = response.headers.get("location")
    except PlaywrightError:
        destination_status = None
        destination_location = None
    return {
        "label": label,
        "present": True,
        "destination_allowed": True,
        "href": href,
        "tab_reachable": tab_steps is not None,
        "tab_steps": tab_steps,
        "enter_opened_expected": enter_opened_expected,
        "destination_status": destination_status,
        "destination_location": destination_location,
    }


def _browser(target, capture_dir):
    origin = urlparse(target["website"])
    pinned_ip = _public_address(origin.hostname) if target.get("custom") else None
    results = []
    capture_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        args = [f"--host-resolver-rules=MAP {origin.hostname} {pinned_ip}", "--disable-features=DnsOverHttps"] if pinned_ip else []
        browser = playwright.chromium.launch(headless=True, args=args)
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
                        and request_url.port in (None, 443)
                        and route.request.method == "GET"
                    ) or (route.request.method == "GET" and target.get("public_link") and _approved_link(route.request.url, target)):
                        route.continue_()
                    else:
                        route.abort()

                context.route("**/*", allow_known_origin)
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
                    probe = _public_link_probe(page, target) if width == 768 and target.get("public_link") else None
                    results.append({
                        "viewport": width,
                        "http_status": response.status if response else None,
                        "page_errors": errors[:5],
                        "screenshot": f"{width}.png",
                        **({"public_link_probe": probe} if probe is not None else {}),
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
    if isinstance(target_id, dict):
        target = target_id
        if not target.get("custom"):
            raise ValueError("Projet non connecté")
        normalize_repository(target["repository"])
        normalize_website(target["website"])
        project_id = target["id"]
    elif target_id in TARGETS:
        target = TARGETS[target_id]
        project_id = target_id
    else:
        raise ValueError("Projet non connecté")
    repository = _repository(target)
    production_sha = _production(target)
    return {
        "target": project_id,
        "project_notes": target.get("notes", ""),
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
            "Le lien public de repli est vérifié par Tab, Entrée et GET ; formulaire non soumis." if target.get("public_link") else "Aucun lien sortant ni formulaire n’a été activé.",
            "Provenance de production non configurée pour ce projet." if not target.get("production_manifest") else "Provenance de production lue dans le manifeste configuré.",
            "Les ressources hébergées sur d’autres domaines sont bloquées ; le rendu peut être incomplet." if target.get("custom") else "Les ressources externes non prévues sont bloquées.",
        ],
    }
