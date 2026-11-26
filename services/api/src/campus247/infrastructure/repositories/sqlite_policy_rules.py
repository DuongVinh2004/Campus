"""SQLite store for executable policy rules: drafts, reviews, immutable versions, vectors, stats, previews, audit."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from campus247.ports.policy_rules import Conflict

SCHEMA = """
CREATE TABLE IF NOT EXISTS rule_drafts(id TEXT PRIMARY KEY, rule_id TEXT NOT NULL, body TEXT NOT NULL,
  author_subject_id TEXT NOT NULL, origin TEXT NOT NULL, row_version INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rule_reviews(id TEXT PRIMARY KEY, draft_id TEXT NOT NULL, reviewer_subject_id TEXT NOT NULL,
  verdict TEXT NOT NULL, note TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rule_versions(rule_id TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL,
  content_sha256 TEXT NOT NULL, graph_version TEXT NOT NULL, release_id TEXT NOT NULL, binding_sha256 TEXT NOT NULL,
  status TEXT NOT NULL, published_by TEXT NOT NULL, published_at TEXT NOT NULL, retired_at TEXT, source_hashes TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY(rule_id, version));
CREATE TABLE IF NOT EXISTS rule_test_vectors(rule_id TEXT NOT NULL, version INTEGER NOT NULL, vector_id TEXT NOT NULL,
  origin TEXT NOT NULL, inputs TEXT NOT NULL, expected TEXT NOT NULL, source_span TEXT, verdict TEXT,
  PRIMARY KEY(rule_id, version, vector_id));
CREATE TABLE IF NOT EXISTS rule_evaluations_stats(day TEXT NOT NULL, topic TEXT NOT NULL, outcome TEXT NOT NULL,
  n INTEGER NOT NULL, PRIMARY KEY(day, topic, outcome));
CREATE TABLE IF NOT EXISTS rule_previews(preview_id TEXT PRIMARY KEY, actor TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL,
  payload_hash TEXT NOT NULL, expires_at TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS rule_idempotency(idempotency_key TEXT NOT NULL, actor TEXT NOT NULL, result TEXT NOT NULL,
  PRIMARY KEY(idempotency_key, actor));
CREATE TABLE IF NOT EXISTS rule_audit(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor TEXT NOT NULL,
  action TEXT NOT NULL, rule_id TEXT, version INTEGER, detail TEXT NOT NULL);
"""


class PolicyRulesStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._tx() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def _tx(self):
        with self._lock:
            db = sqlite3.connect(self.path, timeout=5)
            db.row_factory = sqlite3.Row
            try:
                db.execute("PRAGMA busy_timeout=5000")
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
            finally:
                db.close()

    # ---- drafts
    def put_draft(self, draft_id, rule_id, body, author, origin, now):
        with self._tx() as db:
            db.execute("INSERT INTO rule_drafts VALUES(?,?,?,?,?,?,?,?)",
                (draft_id, rule_id, json.dumps(body, ensure_ascii=False), author, origin, 1, now, now))

    def get_draft(self, draft_id):
        with self._tx() as db:
            row = db.execute("SELECT * FROM rule_drafts WHERE id=?", (draft_id,)).fetchone()
        return _draft(row) if row else None

    def update_draft(self, draft_id, body, row_version, now):
        with self._tx() as db:
            cur = db.execute("UPDATE rule_drafts SET body=?, row_version=row_version+1, updated_at=? WHERE id=? AND row_version=?",
                (json.dumps(body, ensure_ascii=False), now, draft_id, row_version))
            if cur.rowcount != 1:
                raise Conflict("DRAFT_VERSION_CONFLICT")

    def list_drafts(self):
        with self._tx() as db:
            rows = db.execute("SELECT * FROM rule_drafts ORDER BY updated_at DESC").fetchall()
        return [_draft(r) for r in rows]

    def add_review(self, review_id, draft_id, reviewer, verdict, note, now):
        with self._tx() as db:
            db.execute("INSERT INTO rule_reviews VALUES(?,?,?,?,?,?)", (review_id, draft_id, reviewer, verdict, note, now))

    def reviews(self, draft_id):
        with self._tx() as db:
            rows = db.execute("SELECT * FROM rule_reviews WHERE draft_id=? ORDER BY at", (draft_id,)).fetchall()
        return [dict(r) for r in rows]

    # ---- versions
    def latest_version(self, rule_id):
        with self._tx() as db:
            row = db.execute("SELECT * FROM rule_versions WHERE rule_id=? ORDER BY version DESC LIMIT 1", (rule_id,)).fetchone()
        return _version(row) if row else None

    def get_version(self, rule_id, version):
        with self._tx() as db:
            row = db.execute("SELECT * FROM rule_versions WHERE rule_id=? AND version=?", (rule_id, version)).fetchone()
        return _version(row) if row else None

    def add_version(self, rule_id, version, body, sha, graph_version, release_id, binding, status, published_by, now, source_hashes):
        with self._tx() as db:
            try:
                db.execute("INSERT INTO rule_versions VALUES(?,?,?,?,?,?,?,?,?,?,NULL,?)",
                    (rule_id, version, json.dumps(body, ensure_ascii=False), sha, graph_version, release_id, binding, status,
                     published_by, now, json.dumps(source_hashes)))
            except sqlite3.IntegrityError:
                raise Conflict("VERSION_EXISTS") from None

    def set_status(self, rule_id, version, status, now=None):
        with self._tx() as db:
            db.execute("UPDATE rule_versions SET status=?, retired_at=COALESCE(?, retired_at) WHERE rule_id=? AND version=?",
                (status, now if status == "RETIRED" else None, rule_id, version))

    def current_records(self, statuses=("PUBLISHED", "STALE")):
        """Latest version per rule whose status is in `statuses`."""
        with self._tx() as db:
            rows = db.execute("""SELECT v.* FROM rule_versions v JOIN
                (SELECT rule_id, MAX(version) mv FROM rule_versions GROUP BY rule_id) m
                ON v.rule_id=m.rule_id AND v.version=m.mv""").fetchall()
        return [_version(r) for r in rows if r["status"] in statuses]

    def versions(self, rule_id):
        with self._tx() as db:
            rows = db.execute("SELECT * FROM rule_versions WHERE rule_id=? ORDER BY version", (rule_id,)).fetchall()
        return [_version(r) for r in rows]

    # ---- vectors, stats
    def replace_vectors(self, rule_id, version, vectors):
        with self._tx() as db:
            db.execute("DELETE FROM rule_test_vectors WHERE rule_id=? AND version=?", (rule_id, version))
            db.executemany("INSERT INTO rule_test_vectors VALUES(?,?,?,?,?,?,?,?)",
                [(rule_id, version, v["vector_id"], v["origin"], json.dumps(v["inputs"], ensure_ascii=False),
                  json.dumps(v["expected"], ensure_ascii=False), json.dumps(v.get("source_span"), ensure_ascii=False) if v.get("source_span") else None,
                  v.get("verdict")) for v in vectors])

    def vectors(self, rule_id, version):
        with self._tx() as db:
            rows = db.execute("SELECT * FROM rule_test_vectors WHERE rule_id=? AND version=?", (rule_id, version)).fetchall()
        return [{"vector_id": r["vector_id"], "origin": r["origin"], "inputs": json.loads(r["inputs"]),
                 "expected": json.loads(r["expected"]), "source_span": json.loads(r["source_span"]) if r["source_span"] else None,
                 "verdict": r["verdict"]} for r in rows]

    def bump(self, day, topic, outcome):
        with self._tx() as db:
            db.execute("INSERT INTO rule_evaluations_stats VALUES(?,?,?,1) ON CONFLICT(day,topic,outcome) DO UPDATE SET n=n+1", (day, topic, outcome))

    def stats(self, day_from):
        with self._tx() as db:
            rows = db.execute("SELECT day, topic, outcome, n FROM rule_evaluations_stats WHERE day>=? ORDER BY day", (day_from,)).fetchall()
        return [dict(r) for r in rows]

    # ---- previews / idempotency / audit
    def save_preview(self, preview_id, actor, kind, payload, payload_hash, expires_at):
        with self._tx() as db:
            db.execute("INSERT INTO rule_previews VALUES(?,?,?,?,?,?,0)", (preview_id, actor, kind, json.dumps(payload, ensure_ascii=False), payload_hash, expires_at))

    def take_preview(self, preview_id, actor, idempotency_key, now, token_check):
        """-> ('replay', result) | ('ok', kind, payload). Raises KeyError / PermissionError."""
        with self._tx() as db:
            done = db.execute("SELECT result FROM rule_idempotency WHERE idempotency_key=? AND actor=?", (idempotency_key, actor)).fetchone()
            if done:
                return ("replay", json.loads(done["result"]))
            row = db.execute("SELECT * FROM rule_previews WHERE preview_id=?", (preview_id,)).fetchone()
            if row is None or row["used"] or row["actor"] != actor or row["expires_at"] < now:
                raise KeyError(preview_id)
            if not token_check(row["payload_hash"]):
                raise PermissionError("token")
            db.execute("UPDATE rule_previews SET used=1 WHERE preview_id=?", (preview_id,))
            return ("ok", row["kind"], json.loads(row["payload"]))

    def remember(self, idempotency_key, actor, result):
        with self._tx() as db:
            db.execute("INSERT OR REPLACE INTO rule_idempotency VALUES(?,?,?)", (idempotency_key, actor, json.dumps(result, ensure_ascii=False)))

    def audit(self, at, actor, action, rule_id=None, version=None, detail=None):
        with self._tx() as db:
            db.execute("INSERT INTO rule_audit(at,actor,action,rule_id,version,detail) VALUES(?,?,?,?,?,?)",
                (at, actor, action, rule_id, version, json.dumps(detail or {}, ensure_ascii=False)))

    def audit_rows(self, limit=100):
        with self._tx() as db:
            rows = db.execute("SELECT * FROM rule_audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(r), "detail": json.loads(r["detail"])} for r in rows]


def _draft(row):
    return {"id": row["id"], "rule_id": row["rule_id"], "body": json.loads(row["body"]), "author_subject_id": row["author_subject_id"],
        "origin": row["origin"], "row_version": row["row_version"], "created_at": row["created_at"], "updated_at": row["updated_at"]}


def _version(row):
    return {"rule_id": row["rule_id"], "version": row["version"], "body": json.loads(row["body"]), "content_sha256": row["content_sha256"],
        "graph_version": row["graph_version"], "release_id": row["release_id"], "binding_sha256": row["binding_sha256"], "status": row["status"],
        "published_by": row["published_by"], "published_at": row["published_at"], "retired_at": row["retired_at"],
        "source_hashes": json.loads(row["source_hashes"] or "{}")}
