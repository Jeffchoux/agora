"""Bounded, offline import of non-secret profiles into one private installation."""

import fcntl
import json
import os
import re
import secrets
import stat
from pathlib import Path
from urllib.parse import urlsplit

from agora.config import validate_profiles

MAX_BYTES = 65536


class ImportError(ValueError):
    """Safe diagnostics containing no imported content."""


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ImportError("Duplicate JSON fields are not allowed.")
        result[key] = value
    return result


def _read(fd, private=False):
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
        raise ImportError("Profile files must be regular JSON files of at most 64 KiB.")
    if private and (info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1):
        raise ImportError("agents.json must be private, owned by you, and not linked (mode 0600).")
    data = os.read(fd, MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ImportError("Profile files must be at most 64 KiB.")
    return json.loads(data, object_pairs_hook=_object)


def _validate(data):
    # Validate optional values before the shared runtime validator. Imported
    # credential references never read, create, or modify the credential file.
    if not isinstance(data, dict) or len(data) > 32:
        raise ImportError("Expected at most 32 agent profiles.")
    for profile in data.values():
        if not isinstance(profile, dict):
            raise ImportError("Invalid agent profile.")
        for field in ("label", "model"):
            if not isinstance(profile.get(field), str) or not profile[field].strip():
                raise ImportError("Agent label and model must not be empty.")
        if "operator_authorized" in profile and type(profile["operator_authorized"]) is not bool:
            raise ImportError("Authorization must be a boolean.")
        if "key_env" in profile and (not isinstance(profile["key_env"], str) or
                not re.fullmatch(r"[A-Z_][A-Z0-9_]{0,127}", profile["key_env"])):
            raise ImportError("key_env must name an environment variable, never contain a key.")
        if "credential_file" in profile:
            value = profile["credential_file"]
            if (not isinstance(value, str) or not value.startswith(("/", "~/")) or
                    len(value) > 4096 or any(ord(c) < 32 for c in value) or
                    "://" in value or Path(value).name in {"", ".", ".."}):
                raise ImportError("credential_file must be an absolute or home-relative file path.")
        if "endpoint" in profile:
            value = profile["endpoint"]
            if not isinstance(value, str) or len(value) > 2048:
                raise ImportError("Invalid endpoint.")
            url = urlsplit(value)
            if not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ImportError("Endpoints must not include credentials, query parameters, or fragments.")
    try:
        validate_profiles(data)
    except (ValueError, TypeError):
        raise ImportError("Invalid agent configuration; only credential file references are allowed for secrets.") from None


def import_agents(source, directory, authorize_external=False):
    """Merge once, without overwriting IDs, provider calls, or secret access."""
    directory = Path(directory).expanduser().absolute()
    directory_fd = target_fd = source_fd = None
    temporary = None
    try:
        source_fd = os.open(Path(source).expanduser(), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        incoming = _read(source_fd)
        if not isinstance(incoming, dict) or not incoming or len(incoming) > 32:
            raise ImportError("Import must contain 1 to 32 profiles.")
        for profile in incoming.values():
            if not isinstance(profile, dict):
                raise ImportError("Invalid agent profile.")
            if "operator_authorized" in profile and type(profile["operator_authorized"]) is not bool:
                raise ImportError("Authorization must be a boolean.")
            if profile.get("provider") != "ollama":
                if not authorize_external:
                    raise ImportError("External agents require --authorize-external, even if the export claims authorization.")
                profile["operator_authorized"] = True
            if profile.get("credential_file") == "~/.config/agora/credentials.json":
                profile["credential_file"] = str(directory / "credentials.json")
        _validate(incoming)
        if directory.resolve() != directory:
            raise ImportError("Installation directory must not contain symlinks.")
        directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        info = os.fstat(directory_fd)
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ImportError("Installation directory must be owned by you and private (mode 0700).")
        target_fd = os.open("agents.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
        fcntl.flock(target_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        before = os.fstat(target_fd)
        existing = _read(target_fd, private=True)
        _validate(existing)
        if set(existing) & set(incoming):
            raise ImportError("An imported agent ID already exists; no profiles were changed.")
        merged = existing | incoming
        _validate(merged)
        encoded = (json.dumps(merged, ensure_ascii=False, indent=2) + "\n").encode()
        if len(encoded) > MAX_BYTES:
            raise ImportError("Merged configuration exceeds 64 KiB.")
        temporary = ".agents-import-" + secrets.token_hex(16)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd)
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        current = os.stat("agents.json", dir_fd=directory_fd, follow_symlinks=False)
        if (current.st_dev, current.st_ino, current.st_mtime_ns, current.st_size) != (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size):
            raise ImportError("agents.json changed during import; retry after the other editor finishes.")
        os.replace(temporary, "agents.json", src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        temporary = None
        return len(incoming)
    except ImportError:
        raise
    except (OSError, ValueError, TypeError, RecursionError):
        raise ImportError("Cannot import profiles. Check JSON, file size, ownership, permissions and symlinks; no imported content was printed.") from None
    finally:
        if temporary is not None and directory_fd is not None:
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except OSError:
                pass  # Cleanup errors must not expose filesystem diagnostics.
        for fd in (target_fd, source_fd, directory_fd):
            if fd is not None:
                os.close(fd)
