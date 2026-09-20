"""A portable client: no model credentials are sent to Agora."""

import json
from pathlib import Path
from urllib.parse import urlparse

import httpx


class Client:
    def __init__(self, config):
        self.config = (
            json.loads(Path(config).read_text())
            if isinstance(config, (str, Path))
            else config
        )
        url = self.config["url"].rstrip("/")
        parsed = urlparse(url)
        if parsed.scheme != "https" and not (
            parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        ):
            raise ValueError("HTTPS required except loopback SSH tunnels")
        self.http = httpx.Client(
            base_url=url,
            headers={"Authorization": "Bearer " + self.config["token"]},
            timeout=30,
            follow_redirects=False,
        )

    def exchange(self, **data):
        result = self.http.post("/v1/exchange", json=data)
        result.raise_for_status()
        return result.json()

    def close(self):
        self.http.close()
