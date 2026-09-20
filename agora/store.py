"""Durable project board. No model, shell or outbound network access."""

import hashlib
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class Denied(Exception):
    pass


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, brief TEXT NOT NULL,
              max_messages INTEGER NOT NULL, max_depth INTEGER NOT NULL, active INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS members(project TEXT, agent TEXT, token_hash TEXT UNIQUE,
              enabled INTEGER DEFAULT 1, PRIMARY KEY(project,agent));
            CREATE TABLE IF NOT EXISTS messages(seq INTEGER PRIMARY KEY AUTOINCREMENT,
              id TEXT UNIQUE, project TEXT, sender TEXT, recipient TEXT, kind TEXT,
              body TEXT, parent TEXT, depth INTEGER, request_key TEXT, created REAL,
              UNIQUE(project,sender,request_key));
            CREATE TABLE IF NOT EXISTS claims(message TEXT PRIMARY KEY, agent TEXT,
              until REAL, lease TEXT, completed INTEGER DEFAULT 0);
            """)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def create_project(self, project, brief, max_messages=100, max_depth=12):
        if (
            not project
            or len(project) > 80
            or not 1 <= max_messages <= 1000
            or not 1 <= max_depth <= 30
        ):
            raise ValueError("invalid project limits")
        with self.db() as db:
            db.execute(
                "INSERT INTO projects(id,brief,max_messages,max_depth) VALUES(?,?,?,?)",
                (project, brief[:16000], max_messages, max_depth),
            )

    def invite(self, project, agent):
        token = secrets.token_urlsafe(32)
        if not agent or len(agent) > 80:
            raise ValueError("invalid agent")
        with self.db() as db:
            if not db.execute(
                "SELECT 1 FROM projects WHERE id=?", (project,)
            ).fetchone():
                raise Denied("unknown project")
            db.execute(
                "INSERT INTO members(project,agent,token_hash) VALUES(?,?,?)",
                (project, agent, hashlib.sha256(token.encode()).hexdigest()),
            )
        return token

    def authenticate(self, token):
        with self.db() as db:
            row = db.execute(
                "SELECT project,agent FROM members WHERE token_hash=? AND enabled=1",
                (hashlib.sha256(token.encode()).hexdigest(),),
            ).fetchone()
            if not row:
                raise Denied("invalid credential")
            return dict(row)

    def _authorize(self, db, identity):
        row = db.execute(
            "SELECT p.* FROM projects p JOIN members m ON p.id=m.project "
            "WHERE p.id=? AND m.agent=? AND m.enabled=1 AND p.active=1",
            (identity["project"], identity["agent"]),
        ).fetchone()
        if not row:
            raise Denied("project paused or membership revoked")
        return row

    def board(self, identity, after=0, inbox=False):
        with self.db() as db:
            project = self._authorize(db, identity)
            sql = "SELECT * FROM messages WHERE project=? AND seq>?"
            params = [identity["project"], after]
            if inbox:
                sql += " AND recipient=?"
                params.append(identity["agent"])
            rows = db.execute(sql + " ORDER BY seq LIMIT 100", params).fetchall()
            members = [
                r[0]
                for r in db.execute(
                    "SELECT agent FROM members WHERE project=? AND enabled=1",
                    (identity["project"],),
                )
            ]
            return {
                "project": dict(project),
                "participants": members,
                "messages": [dict(r) for r in rows],
            }

    def post(self, identity, recipient, kind, body, request_key, parent=None):
        if kind not in {"task", "question", "answer", "artifact", "review"}:
            raise ValueError("invalid kind")
        if not isinstance(body, str) or not 1 <= len(body) <= 16000:
            raise ValueError("body must contain 1..16000 characters")
        if not isinstance(request_key, str) or not 1 <= len(request_key) <= 100:
            raise ValueError("idempotency key required")
        if not isinstance(recipient, str) or recipient == identity["agent"]:
            raise ValueError("select another participant")
        project, sender = identity["project"], identity["agent"]
        with self.db() as db:
            limits = self._authorize(db, identity)
            existing = db.execute(
                "SELECT * FROM messages WHERE project=? AND sender=? AND request_key=?",
                (project, sender, request_key),
            ).fetchone()
            if existing:
                if any(
                    existing[k] != v
                    for k, v in {
                        "recipient": recipient,
                        "kind": kind,
                        "body": body,
                        "parent": parent,
                    }.items()
                ):
                    raise Denied("idempotency conflict")
                return dict(existing)
            if not db.execute(
                "SELECT 1 FROM members WHERE project=? AND agent=? AND enabled=1",
                (project, recipient),
            ).fetchone():
                raise Denied("recipient not a project member")
            depth = 0
            if parent:
                prior = db.execute(
                    "SELECT * FROM messages WHERE id=? AND project=?", (parent, project)
                ).fetchone()
                if not prior:
                    raise Denied("parent not in project")
                depth = prior["depth"] + 1
            if depth > limits["max_depth"]:
                raise Denied("conversation depth exhausted")
            count = db.execute(
                "SELECT count(*) FROM messages WHERE project=?", (project,)
            ).fetchone()[0]
            if count >= limits["max_messages"]:
                raise Denied("project message budget exhausted")
            mid = str(uuid.uuid4())
            db.execute(
                "INSERT INTO messages(id,project,sender,recipient,kind,body,parent,depth,request_key,created) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    mid,
                    project,
                    sender,
                    recipient,
                    kind,
                    body,
                    parent,
                    depth,
                    request_key,
                    time.time(),
                ),
            )
            return dict(
                db.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
            )

    def claim(self, identity, message, complete=False, lease=None):
        with self.db() as db:
            self._authorize(db, identity)
            row = db.execute(
                "SELECT * FROM messages WHERE id=? AND project=? AND recipient=?",
                (message, identity["project"], identity["agent"]),
            ).fetchone()
            if not row:
                raise Denied("not assigned to this agent")
            old = db.execute(
                "SELECT * FROM claims WHERE message=?", (message,)
            ).fetchone()
            now = time.time()
            if complete:
                if (
                    not old
                    or old["agent"] != identity["agent"]
                    or old["until"] < now
                    or old["lease"] != lease
                ):
                    raise Denied("valid claim required")
                db.execute("UPDATE claims SET completed=1 WHERE message=?", (message,))
            else:
                if old and (old["completed"] or old["until"] > now):
                    raise Denied("already claimed or completed")
                lease = secrets.token_urlsafe(24)
                db.execute(
                    "INSERT INTO claims(message,agent,until,lease) VALUES(?,?,?,?) "
                    "ON CONFLICT(message) DO UPDATE SET agent=excluded.agent,until=excluded.until,lease=excluded.lease",
                    (message, identity["agent"], now + 180, lease),
                )
            return {
                "message": message,
                "completed": complete,
                "lease_seconds": 180,
                "lease": lease,
            }

    def dispatch(self, identity, data):
        if not isinstance(data, dict):
            raise TypeError("JSON object required")
        operation = data.get("operation")
        if operation == "board":
            after = data.get("after", 0)
            if not isinstance(after, int) or after < 0:
                raise ValueError("invalid cursor")
            return self.board(identity, after, data.get("inbox") is True)
        if operation == "post":
            return self.post(
                identity,
                **{
                    k: data.get(k)
                    for k in ["recipient", "kind", "body", "request_key", "parent"]
                },
            )
        if operation in {"claim", "complete"}:
            return self.claim(
                identity,
                data.get("message"),
                operation == "complete",
                data.get("lease"),
            )
        raise ValueError("unknown operation")
