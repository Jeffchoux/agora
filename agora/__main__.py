import argparse
import json
import os
import secrets
from pathlib import Path

from agora.client import Client
from agora.store import Store


def main():
    p = argparse.ArgumentParser(
        description="Agora — projets et collaboration inter-agents"
    )
    p.add_argument("--db", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)
    setup = sub.add_parser("init", help="Create private local installation files")
    setup.add_argument("--directory", default=str(Path.home() / ".config" / "agora"))
    imported = sub.add_parser("import-agents", help="Import non-secret profiles without replacing existing agents")
    imported.add_argument("path")
    imported.add_argument("--directory", default=str(Path.home() / ".config" / "agora"))
    imported.add_argument("--authorize-external", action="store_true", help="Authorize use of your own external provider accounts")
    start = sub.add_parser("start", help="Start your local console and mission runner together")
    start.add_argument("--directory", default=str(Path.home() / ".config" / "agora"))
    start.add_argument("--port", type=int, default=8768)
    c = sub.add_parser("create")
    c.add_argument("project")
    c.add_argument("--brief-file", required=True)
    c.add_argument("--max-messages", type=int, default=100)
    i = sub.add_parser("invite")
    i.add_argument("project")
    i.add_argument("agent")
    i.add_argument("--out", required=True)
    i.add_argument("--url", default="http://127.0.0.1:8768")
    e = sub.add_parser("exchange")
    e.add_argument("--config", required=True)
    e.add_argument("--file", required=True)
    b = sub.add_parser("board")
    b.add_argument("--config", required=True)
    w = sub.add_parser("worker")
    w.add_argument("--config", required=True)
    w.add_argument("--model-config", required=True)
    w.add_argument("--turns", type=int, default=1)
    w.add_argument("--seconds", type=int, default=180)
    z = sub.add_parser("pause")
    z.add_argument("project")
    r = sub.add_parser("revoke")
    r.add_argument("project")
    r.add_argument("agent")
    a = p.parse_args()
    os.umask(0o077)
    if a.cmd == "import-agents":
        from agora.import_profiles import ImportError, import_agents

        try:
            count = import_agents(a.path, a.directory, a.authorize_external)
        except ImportError as error:
            p.error(str(error))
        print(f"Imported {count} agent profile(s). Restart Agora to load them. No provider was contacted.")
        return
    if a.cmd == "start":
        from agora.launcher import StartupError, start_local

        if a.db is not None:
            p.error("start uses its private directory; use --directory instead of --db")
        try:
            start_local(a.directory, a.port)
        except StartupError as error:
            p.error(str(error))
        return
    a.db = a.db or os.environ.get("AGORA_DB", "state/agora.sqlite")
    if a.cmd == "init":
        directory = Path(a.directory).expanduser()
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o077:
            raise ValueError("Choose a private directory owned by your account (mode 0700)")
        files = {"operator.key": secrets.token_urlsafe(32) + "\n", "agents.json": "{}\n", "credentials.json": "{}\n"}
        for name, content in files.items():
            target = directory / name
            if not target.exists():
                with target.open("x") as f:
                    f.write(content)
        print("Private configuration ready: " + str(directory))
        print("Open operator.key locally to sign in. Add your own profiles to agents.json; no provider has been activated.")
    elif a.cmd == "create":
        Store(a.db).create_project(
            a.project, Path(a.brief_file).read_text(), a.max_messages
        )
        print("Projet créé : " + a.project)
    elif a.cmd == "invite":
        target = Path(a.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Never overwrite credentials. A file error must not silently rotate an existing agent.
        with target.open("x") as f:
            token = Store(a.db).invite(a.project, a.agent)
            json.dump(
                {"url": a.url, "project": a.project, "agent": a.agent, "token": token},
                f,
            )
        print(
            "Invitation enregistrée dans "
            + str(target)
            + " (ne pas publier ce fichier)."
        )
    elif a.cmd in {"exchange", "board"}:
        client = Client(a.config)
        try:
            print(
                json.dumps(
                    client.exchange(
                        **(
                            json.loads(Path(a.file).read_text())
                            if a.cmd == "exchange"
                            else {"operation": "board"}
                        )
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        finally:
            client.close()
    elif a.cmd == "worker":
        from agora.worker import run

        print(json.dumps(run(a.config, a.model_config, a.turns, a.seconds)))
    elif a.cmd == "pause":
        with Store(a.db).db() as db:
            db.execute("UPDATE projects SET active=0 WHERE id=?", (a.project,))
        print("Projet suspendu")
    elif a.cmd == "revoke":
        with Store(a.db).db() as db:
            db.execute(
                "UPDATE members SET enabled=0 WHERE project=? AND agent=?",
                (a.project, a.agent),
            )
        print("Accès révoqué")


if __name__ == "__main__":
    main()
