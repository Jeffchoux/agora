"""Install the dedicated /agora/ route without replacing any existing route."""

import hashlib
import subprocess
from pathlib import Path

path = Path("/etc/caddy/Caddyfile")
original = path.read_text()
anchor = "app.galaxia-os.com {\n"
block = """\t# BEGIN AGORA — isolated authenticated project gateway
\thandle_path /agora/* {
\t\treverse_proxy 127.0.0.1:8768
\t}
\t# END AGORA
"""
if block in original:
    print("Agora route already installed")
else:
    if original.count(anchor) != 1 or "# BEGIN AGORA" in original:
        raise SystemExit(
            "Unexpected Caddy structure: preserving existing configuration"
        )
    digest = hashlib.sha256(original.encode()).hexdigest()[:16]
    backup = Path("/etc/caddy/Caddyfile.before-agora-" + digest)
    backup.write_text(original)
    backup.chmod(0o600)
    candidate = Path("/etc/caddy/Caddyfile.agora-candidate")
    candidate.write_text(original.replace(anchor, anchor + block, 1))
    candidate.chmod(0o600)
    subprocess.run(
        ["caddy", "validate", "--config", str(candidate), "--adapter", "caddyfile"],
        check=True,
    )
    if path.read_text() != original:
        raise SystemExit("Concurrent Caddy change: retry after review")
    try:
        path.write_text(candidate.read_text())
        subprocess.run(["systemctl", "reload", "caddy"], check=True)
    except Exception:
        path.write_text(original)
        subprocess.run(["systemctl", "reload", "caddy"], check=True)
        raise
    finally:
        candidate.unlink(missing_ok=True)
    print("Dedicated Agora HTTPS route installed; other routes preserved")
