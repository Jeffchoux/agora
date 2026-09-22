"""One foreground, loopback-only installation; no provider discovery or login."""

import contextlib
import fcntl
import os
import shlex
import signal
import socket
import stat
import threading
from pathlib import Path

import uvicorn

from agora.config import profiles


class StartupError(Exception):
    """Safe, operator-actionable diagnostics, never raw provider/file contents."""


def private_file(path):
    try:
        info = path.lstat()
        valid = stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
        valid = valid and not info.st_mode & 0o077
    except OSError:
        valid = False
    if not valid:
        raise StartupError(f"{path.name} must be a regular private file owned by you (mode 0600).")


@contextlib.contextmanager
def installation(directory):
    """Explicit directory wins over old service environment; restore on return."""
    values = {
        "AGORA_ADMIN_TOKEN_FILE": str(directory / "operator.key"),
        "AGORA_AGENTS_FILE": str(directory / "agents.json"),
        "AGORA_DB": str(directory / "agora.sqlite"),
        "AGORA_LEGACY_INSTALLATION": "0",
    }
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def start_local(directory, port=8768):
    """Serve one private installation until Ctrl+C; finish the current runner step."""
    if not 1 <= port <= 65535:
        raise StartupError("Choose a port between 1 and 65535 with --port.")
    directory = Path(directory).expanduser().absolute()
    if not directory.is_dir():
        raise StartupError(
            "Configuration missing. Run: uv run --no-sync python -m agora init --directory "
            + shlex.quote(str(directory))
        )
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise StartupError("Choose a private directory owned by you (mode 0700), not a symlink.")
    for name in ("operator.key", "agents.json"):
        private_file(directory / name)
    try:
        key_file = directory / "operator.key"
        if key_file.stat().st_size > 4096:
            raise ValueError
        key = key_file.read_text().strip()
        if len(key) < 32 or not key.isascii() or not key.isprintable():
            raise ValueError
    except (OSError, ValueError):
        raise StartupError("operator.key is unreadable or invalid; restore your private access key.") from None
    for name in ("agora.sqlite", "agora.sqlite-wal", "agora.sqlite-shm", "agora.runner.lock"):
        path = directory / name
        if path.exists() or path.is_symlink():
            private_file(path)

    with installation(directory):
        try:
            count = len(profiles({}))
        except (OSError, ValueError, TypeError):
            raise StartupError("Invalid agents.json. Check the private profile examples in docs/INSTALL.en.md.") from None
        try:
            with socket.socket() as listener:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                # Keep the socket: no check-then-bind race, no unrelated process stopped.
                listener.bind(("127.0.0.1", port))
                with (directory / "agora.runner.lock").open("a") as lock:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        raise StartupError("A runner already owns this database. Stop it before using start.") from None
                    serve(directory, listener, count)
        except OSError:
            raise StartupError(
                "Could not start locally. Check directory access and whether the port is already in use; "
                "choose another with --port. No existing service was stopped."
            ) from None


def serve(directory, listener, count):
    # Import after selecting the installation; keep the standalone service entrypoints unchanged.
    from agora.mission_runner import step
    from agora.missions import Missions
    from agora.server import create_app
    from agora.store import Store

    url = f"http://127.0.0.1:{listener.getsockname()[1]}"
    try:
        app = create_app(url=url)
        missions = Missions(Store(directory / "agora.sqlite"))
    except Exception:  # noqa: BLE001 — configuration/database errors must not expose private contents
        raise StartupError("Cannot open this installation. Check its database and profiles; existing files were not replaced.") from None
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False))
    stop = threading.Event()
    failed = threading.Event()

    def run_missions():
        try:
            while not server.started:
                if stop.wait(0.05) or server.should_exit:
                    return
            missions.recover()
            print(f"Agora ready: {url}", flush=True)
            print(f"Sign in by choosing {directory / 'operator.key'} in the console.", flush=True)
            print(f"{count} configured agent(s). Profiles are not availability or quota checks.", flush=True)
            if not count:
                print("Explore the examples now. Add your agents to agents.json, then restart to run a mission.", flush=True)
            print("Previously queued missions resume. Ctrl+C stops both services after the current step.", flush=True)
            while not stop.is_set() and not server.should_exit:
                if not step(missions):
                    stop.wait(0.25)
        except Exception:  # noqa: BLE001 — stop both services without logging provider diagnostics
            failed.set()
            server.should_exit = True

    def request_stop(signum, frame):
        stop.set()
        server.should_exit = True

    # Uvicorn replays captured signals after shutdown. Preserve orderly runner cleanup.
    previous = {sig: signal.signal(sig, request_stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    runner = threading.Thread(target=run_missions, name="agora-runner")
    try:
        runner.start()
        server.run(sockets=[listener])
    finally:
        stop.set()
        if runner.is_alive():
            print("Stopping Agora; waiting for any in-flight step to finish. No new step will start.", flush=True)
            runner.join()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    if failed.is_set():
        raise StartupError("Mission runner stopped unexpectedly; the console was stopped too. Check this installation before restarting.")
