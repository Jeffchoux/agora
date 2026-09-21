"""Installation-owned agent configuration. Secrets are never returned to the UI."""

import json
import os
import re
from pathlib import Path


def profiles(legacy):
    filename = os.environ.get("AGORA_AGENTS_FILE")
    if not filename:
        return legacy if os.environ.get("AGORA_LEGACY_INSTALLATION") == "1" else {}
    path = Path(filename).expanduser()
    stat = path.stat()
    if stat.st_uid != os.getuid() or stat.st_mode & 0o077 or stat.st_size > 65536:
        raise ValueError("Agent configuration must be private, owned by the operator and bounded")
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or len(data) > 32:
        raise ValueError("Expected at most 32 agent profiles")
    allowed = {"label", "provider", "model", "endpoint", "key_env", "credential_file", "operator_authorized"}
    providers = {"ollama", "codex-cli", "claude-cli", "grok-cli", "openai-compatible", "openrouter-free"}
    for name, profile in data.items():
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", name) or not isinstance(profile, dict):
            raise ValueError("Invalid agent profile")
        if set(profile) - allowed or profile.get("provider") not in providers:
            raise ValueError("Unsupported agent configuration; use credential_file for secrets")
        if any(not isinstance(profile.get(k), str) or not 1 <= len(profile[k]) <= 120 for k in ("label", "model")):
            raise ValueError("Agent label and model required")
        if profile["provider"] != "ollama" and profile.get("operator_authorized") is not True:
            raise ValueError("Explicit authorization required for external agents")
        if profile["provider"] == "openai-compatible" and not str(profile.get("endpoint", "")).startswith("https://"):
            raise ValueError("HTTPS endpoint required")
    return data
