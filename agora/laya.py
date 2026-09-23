"""Optional, advisory-only local Laya bridge. No mission or provider side effects."""

import asyncio
import os
import re
import stat
from pathlib import Path
from threading import Lock

CATEGORIES = {"code", "ux", "product"}
SUGGEST_URL = "http://127.0.0.1:18769/suggest"
QUESTIONS = {
    "specialty": {
        "type": "choice",
        "instructions": "Which specialist should review this project request?",
        "criteria": {
            "code": "Source code, automated tests, programming errors.",
            "ux": "Interface usability, accessibility and visual design.",
            "product": "Business idea, target customers and product strategy.",
        },
    }
}


class Unavailable(Exception):
    pass


class Busy(Exception):
    pass


def private_token(filename):
    """Open without following the final symlink, then validate the actual fd."""
    if not filename or not Path(filename).is_absolute():
        raise ValueError("Private Laya token required")
    fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > 512
        ):
            raise ValueError("Private Laya token required")
        value = handle.read(513).strip()
    if not re.fullmatch(rb"[A-Za-z0-9_-]{32,256}", value):
        raise ValueError("Invalid Laya token")
    return value.decode("ascii")


def configured():
    try:
        private_token(os.environ.get("AGORA_LAYA_TOKEN_FILE"))
        return True
    except (OSError, ValueError):
        return False


def validate_brief(data):
    if not isinstance(data, dict) or set(data) != {"brief"}:
        raise ValueError("Provide a brief of 10–1200 characters")
    brief = data["brief"]
    if not isinstance(brief, str) or not 10 <= len(brief.strip()) <= 1200:
        raise ValueError("Provide a brief of 10–1200 characters")
    return brief.strip()


def suggestion(category):
    if not isinstance(category, str) or category not in CATEGORIES:
        raise ValueError("Invalid Laya response")
    return {"category": category, "engine": "laya-coreml", "experimental": True}


class LayaBridge:
    def __init__(self):
        self.lock = Lock()

    async def suggest(self, brief):
        import httpx

        if not self.lock.acquire(blocking=False):
            raise Busy()
        try:
            try:
                token = private_token(os.environ.get("AGORA_LAYA_TOKEN_FILE"))
            except ValueError:
                raise Unavailable() from None
            async with (
                asyncio.timeout(15),
                httpx.AsyncClient(trust_env=False, timeout=15, follow_redirects=False) as client,
                client.stream(
                    "POST", SUGGEST_URL,
                    headers={"Authorization": "Bearer " + token},
                    json={"brief": brief},
                ) as response,
            ):
                if response.status_code == 429:
                    raise Busy()
                if response.status_code == 400:
                    raise ValueError("Brief exceeds the local model's token budget")
                if response.status_code != 200:
                    raise Unavailable()
                payload = bytearray()
                async for part in response.aiter_bytes(chunk_size=1025):
                    payload.extend(part)
                    if len(payload) > 1024:
                        raise Unavailable()
            import json

            try:
                data = json.loads(payload)
                result = suggestion(data.get("category"))
                if data != result:
                    raise ValueError()
                return result
            except (ValueError, TypeError, AttributeError):
                raise Unavailable() from None
        except (OSError, TimeoutError, httpx.HTTPError):
            raise Unavailable() from None
        finally:
            self.lock.release()
