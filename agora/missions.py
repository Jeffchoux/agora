"""Explicit, durable missions. Reservations survive failures and process restarts."""

import json
import time
import uuid
from pathlib import Path

from agora.inspection import TARGETS, collect
from agora.store import Denied

PROFILES = {
    "codex": {
        "label": "Codex",
        "provider": "codex-cli",
        "model": "gpt-6-astra",
        "operator_authorized": True,
    },
    "grok": {
        "label": "Grok",
        "provider": "grok-cli",
        "model": "default",
        "operator_authorized": True,
    },
    "qwen-coder": {
        "label": "Qwen Coder",
        "provider": "ollama",
        "model": "qwen2.5-coder:7b",
    },
    "mistral": {
        "label": "Mistral local",
        "provider": "ollama",
        "model": "mistral:latest",
    },
    "qwen": {"label": "Qwen 3", "provider": "ollama", "model": "qwen3:8b"},
    "llama": {"label": "Llama", "provider": "ollama", "model": "llama3.1:8b"},
    "dolphin": {"label": "Dolphin", "provider": "ollama", "model": "dolphin3:8b"},
}


class Missions:
    def __init__(self, store, collector=collect):
        self.store = store
        self.collector = collector
        with store.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS missions (
              id TEXT PRIMARY KEY, title TEXT, brief TEXT, agents TEXT,
              max_calls INTEGER, seconds INTEGER, calls INTEGER DEFAULT 0,
              status TEXT DEFAULT 'draft', created REAL, started REAL, deadline REAL,
              error TEXT DEFAULT '', request_key TEXT UNIQUE);
            CREATE TABLE IF NOT EXISTS mission_turns (
              id TEXT PRIMARY KEY, mission TEXT, agent TEXT, ordinal INTEGER,
              status TEXT, body TEXT DEFAULT '', kind TEXT DEFAULT '', created REAL,
              UNIQUE(mission, ordinal));
            CREATE TABLE IF NOT EXISTS mission_context (
              mission TEXT PRIMARY KEY REFERENCES missions(id),
              target TEXT NOT NULL, evidence TEXT);
            """)

    def create(self, title, brief, agents, max_calls, seconds, request_key, target=None):
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 100:
            raise ValueError("Titre requis, 100 caractères maximum")
        if not isinstance(brief, str) or not 10 <= len(brief) <= 8000:
            raise ValueError("Le brief doit contenir 10 à 8 000 caractères")
        if (
            not isinstance(agents, list)
            or not 1 <= len(agents) <= 4
            or len(set(agents)) != len(agents)
            or any(a not in PROFILES for a in agents)
        ):
            raise ValueError("Choisir 1 à 4 agents disponibles")
        if type(max_calls) is not int or not len(agents) <= max_calls <= 12:
            raise ValueError("Prévoir au moins un appel par agent, au plus 12 appels")
        if type(seconds) is not int or not 180 <= seconds <= 1800:
            raise ValueError("Durée entre 3 et 30 minutes")
        if not isinstance(request_key, str) or not 1 <= len(request_key) <= 80:
            raise ValueError("Identifiant de création requis")
        if target is not None and target not in TARGETS:
            raise ValueError("Projet non connecté")
        with self.store.db() as db:
            old = db.execute(
                "SELECT * FROM missions WHERE request_key=?", (request_key,)
            ).fetchone()
            if old:
                old_context = db.execute(
                    "SELECT target FROM mission_context WHERE mission=?", (old["id"],)
                ).fetchone()
                if (
                    old["title"],
                    old["brief"],
                    old["agents"],
                    old["max_calls"],
                    old["seconds"],
                    old_context["target"] if old_context else None,
                ) != (title.strip(), brief, json.dumps(agents), max_calls, seconds, target):
                    raise Denied("Conflit de création")
                return old["id"]
            mid = str(uuid.uuid4())
            db.execute(
                "INSERT INTO missions(id,title,brief,agents,max_calls,seconds,created,request_key) VALUES(?,?,?,?,?,?,?,?)",
                (
                    mid,
                    title.strip(),
                    brief,
                    json.dumps(agents),
                    max_calls,
                    seconds,
                    time.time(),
                    request_key,
                ),
            )
            if target:
                db.execute(
                    "INSERT INTO mission_context(mission,target) VALUES(?,?)",
                    (mid, target),
                )
            return mid

    def list(self):
        with self.store.db() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM missions ORDER BY created DESC LIMIT 100"
                )
            ]

    def detail(self, mid):
        with self.store.db() as db:
            row = db.execute("SELECT * FROM missions WHERE id=?", (mid,)).fetchone()
            if not row:
                raise Denied("Mission introuvable")
            result = dict(row)
            result["agents"] = json.loads(result["agents"])
            result["turns"] = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM mission_turns WHERE mission=? ORDER BY ordinal",
                    (mid,),
                )
            ]
            result["api_budget_usd"] = 0
            context = db.execute(
                "SELECT target,evidence FROM mission_context WHERE mission=?", (mid,)
            ).fetchone()
            result["target"] = context["target"] if context else None
            result["evidence"] = (
                json.loads(context["evidence"])
                if context and context["evidence"]
                else None
            )
            return result

    def action(self, mid, action):
        with self.store.db() as db:
            row = db.execute("SELECT * FROM missions WHERE id=?", (mid,)).fetchone()
            if not row:
                raise Denied("Mission introuvable")
            if action == "start":
                if row["status"] == "draft":
                    if (
                        db.execute(
                            "SELECT count(*) FROM missions WHERE status IN ('queued','running')"
                        ).fetchone()[0]
                        >= 3
                    ):
                        raise Denied("Trois missions sont déjà en attente ou en cours")
                    db.execute("UPDATE missions SET status='queued' WHERE id=?", (mid,))
            elif action == "stop":
                if row["status"] in ("draft", "queued", "running"):
                    db.execute(
                        "UPDATE missions SET status='stopped' WHERE id=?", (mid,)
                    )
            else:
                raise ValueError("Action inconnue")

    def prepare_next(self):
        """Collect evidence in the runner, not in the memory-limited web service."""
        with self.store.db() as db:
            row = db.execute(
                "SELECT m.id,c.target FROM missions m JOIN mission_context c ON c.mission=m.id "
                "WHERE m.status='queued' AND c.evidence IS NULL ORDER BY m.created LIMIT 1"
            ).fetchone()
        if not row:
            return False
        mid, target = row["id"], row["target"]
        try:
            evidence = self.collector(target, Path(self.store.path).parent / "evidence" / mid)
        except Exception:  # noqa: BLE001 — never publish provider diagnostics or secrets
            with self.store.db() as db:
                db.execute(
                    "UPDATE missions SET status='failed',error=? WHERE id=? AND status='queued'",
                    ("Inspection impossible ; aucun agent appelé.", mid),
                )
            return True
        with self.store.db() as db:
            db.execute(
                "UPDATE mission_context SET evidence=? WHERE mission=? AND evidence IS NULL",
                (json.dumps(evidence, ensure_ascii=False), mid),
            )
        return True

    def reserve(self):
        with self.store.db() as db:
            # No concurrent model calls. Expired reservations remain charged.
            if db.execute(
                "SELECT 1 FROM mission_turns WHERE status='running'"
            ).fetchone():
                return None
            row = db.execute(
                "SELECT * FROM missions WHERE status IN ('running','queued') ORDER BY created LIMIT 1"
            ).fetchone()
            if not row:
                return None
            m = dict(row)
            context = db.execute(
                "SELECT target,evidence FROM mission_context WHERE mission=?", (m["id"],)
            ).fetchone()
            if context and context["target"] and not context["evidence"]:
                return None
            now = time.time()
            if m["status"] == "queued":
                m["deadline"] = now + m["seconds"]
                db.execute(
                    "UPDATE missions SET status='running',started=?,deadline=? WHERE id=?",
                    (now, m["deadline"], m["id"]),
                )
            if m["calls"] >= m["max_calls"] or now + 125 > m["deadline"]:
                db.execute(
                    "UPDATE missions SET status='finished',error=? WHERE id=?",
                    ("Plafond atteint : aucun nouvel appel.", m["id"]),
                )
                return None
            agent = json.loads(m["agents"])[m["calls"] % len(json.loads(m["agents"]))]
            tid = str(uuid.uuid4())
            db.execute("UPDATE missions SET calls=calls+1 WHERE id=?", (m["id"],))
            db.execute(
                "INSERT INTO mission_turns(id,mission,agent,ordinal,status,created) VALUES(?,?,?,?,'running',?)",
                (tid, m["id"], agent, m["calls"] + 1, now),
            )
            prior = [
                dict(r)
                for r in db.execute(
                    "SELECT agent,kind,body FROM mission_turns WHERE mission=? AND status='done' ORDER BY ordinal DESC LIMIT 3",
                    (m["id"],),
                )
            ]
            return {
                "turn": tid,
                "mission": m["id"],
                "agent": agent,
                "brief": m["brief"],
                "previous": list(reversed(prior)),
                "ordinal": m["calls"] + 1,
                "max_calls": m["max_calls"],
                "evidence": json.loads(context["evidence"]) if context and context["evidence"] else None,
            }

    def finish(self, turn, contribution=None):
        with self.store.db() as db:
            row = db.execute(
                "SELECT * FROM mission_turns WHERE id=? AND status='running'", (turn,)
            ).fetchone()
            if not row:
                raise Denied("Réservation inexistante")
            if contribution is None:
                db.execute(
                    "UPDATE mission_turns SET status='failed',body='Le fournisseur n’a pas répondu correctement. Vérifier connexion ou quota.' WHERE id=?",
                    (turn,),
                )
                db.execute(
                    "UPDATE missions SET status='failed',error='Appel échoué ; pas de nouvelle tentative automatique.' WHERE id=? AND status='running'",
                    (row["mission"],),
                )
            else:
                db.execute(
                    "UPDATE mission_turns SET status='done',body=?,kind=? WHERE id=?",
                    (contribution.body, contribution.kind, turn),
                )
                db.execute(
                    "UPDATE missions SET status='finished' WHERE id=? AND calls>=max_calls AND status='running'",
                    (row["mission"],),
                )

    def recover(self):
        with self.store.db() as db:
            db.execute(
                "UPDATE missions SET status='failed',error='Exécution interrompue. Appels réservés conservés ; aucun redémarrage automatique.' WHERE status='running'"
            )
            db.execute(
                "UPDATE mission_turns SET status='failed',body='Exécution interrompue.' WHERE status='running'"
            )
