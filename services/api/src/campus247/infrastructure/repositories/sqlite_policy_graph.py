"""Additive, append-only graph drafts, review history and immutable publications."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from campus247.domain.policy_graph import GraphProposal, ReviewVerdict, fingerprint


from campus247.ports.policy_graph import GraphConflict  # noqa: E402 -- re-exported for existing callers


class SQLitePolicyGraphRepository:
    def __init__(self, path: Path, *, workspace: Path):
        root = workspace.resolve(strict=True)
        target = path.absolute()
        if target.resolve() == root or not target.resolve().is_relative_to(root):
            raise ValueError("graph path outside workspace")
        for parent in (target, *target.parents):
            if parent.exists() and (parent.is_symlink() or parent.is_junction()
                    or getattr(parent.stat(), "st_file_attributes", 0) & 0x400):
                raise ValueError("graph reparse path denied")
            if parent == root:
                break
        self.path = target.resolve()
        self.workspace = root
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS policy_proposal (
                    id TEXT PRIMARY KEY, raw TEXT NOT NULL, digest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS policy_node (
                    graph_id TEXT NOT NULL REFERENCES policy_proposal(id),
                    id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(graph_id,id));
                CREATE TABLE IF NOT EXISTS policy_edge (
                    graph_id TEXT NOT NULL REFERENCES policy_proposal(id),
                    id TEXT NOT NULL, from_id TEXT NOT NULL, to_id TEXT NOT NULL,
                    payload TEXT NOT NULL, PRIMARY KEY(graph_id,id));
                CREATE INDEX IF NOT EXISTS policy_edge_from ON policy_edge(graph_id,from_id);
                CREATE INDEX IF NOT EXISTS policy_edge_to ON policy_edge(graph_id,to_id);
                CREATE TABLE IF NOT EXISTS policy_review (
                    graph_id TEXT NOT NULL REFERENCES policy_proposal(id),
                    revision INTEGER NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(graph_id,revision));
                CREATE TABLE IF NOT EXISTS policy_publication (
                    id TEXT PRIMARY KEY REFERENCES policy_proposal(id),
                    manifest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS policy_extraction (
                    request_id TEXT PRIMARY KEY, raw TEXT NOT NULL, metadata TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS policy_extraction_usage (
                    request_id TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(request_id,revision));
            """)

    @contextmanager
    def connect(self):
        if self.path.resolve() != self.path or not self.path.resolve().is_relative_to(self.workspace):
            raise GraphConflict("GRAPH_PATH_CHANGED")
        for parent in (self.path, *self.path.parents):
            if parent.exists() and (parent.is_symlink() or parent.is_junction()
                    or getattr(parent.stat(), "st_file_attributes", 0) & 0x400):
                raise GraphConflict("GRAPH_PATH_CHANGED")
            if parent == self.workspace:
                break
        db = sqlite3.connect(self.path, timeout=5)
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def record_extraction(self, request_id, raw, metadata):
        with self.connect() as db:
            try:
                db.execute("INSERT INTO policy_extraction VALUES(?,?,?)", (request_id, raw, json.dumps(metadata)))
            except sqlite3.IntegrityError:
                raise GraphConflict("EXTRACTION_ID_EXISTS") from None

    def extraction_usage(self, request_id, payload):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            revision = db.execute("SELECT COALESCE(MAX(revision),0)+1 FROM policy_extraction_usage WHERE request_id=?", (request_id,)).fetchone()[0]
            db.execute("INSERT INTO policy_extraction_usage VALUES(?,?,?)", (request_id, revision, json.dumps(payload)))

    def add(self, proposal: GraphProposal, *, raw: str):
        # Keep the exact extraction payload; no normalized rewrite of a model proposal.
        if GraphProposal.model_validate_json(raw) != proposal:
            raise GraphConflict("RAW_PROPOSAL_MISMATCH")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute("INSERT INTO policy_proposal VALUES(?,?,?)",
                    (proposal.id, raw, fingerprint(proposal.model_dump(mode="json"))))
                db.executemany("INSERT INTO policy_node VALUES(?,?,?)",
                    [(proposal.id, n.id, n.model_dump_json()) for n in proposal.nodes])
                db.executemany("INSERT INTO policy_edge VALUES(?,?,?,?,?)",
                    [(proposal.id, e.id, e.from_id, e.to_id, e.model_dump_json()) for e in proposal.edges])
            except sqlite3.IntegrityError:
                raise GraphConflict("GRAPH_ID_EXISTS_OR_DUPLICATE") from None

    def get(self, graph_id):
        with self.connect() as db:
            row = db.execute("SELECT raw FROM policy_proposal WHERE id=?", (graph_id,)).fetchone()
        return GraphProposal.model_validate_json(row[0]) if row else None

    def raw(self, graph_id):
        with self.connect() as db:
            row = db.execute("SELECT raw FROM policy_proposal WHERE id=?", (graph_id,)).fetchone()
        return row[0] if row else None

    def reviews(self, graph_id):
        with self.connect() as db:
            rows = db.execute("SELECT revision,payload FROM policy_review WHERE graph_id=? ORDER BY revision", (graph_id,)).fetchall()
        return [(rev, ReviewVerdict.model_validate_json(payload)) for rev, payload in rows]

    def review(self, graph_id, verdict: ReviewVerdict, *, expected_revision):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            graph = db.execute("SELECT raw FROM policy_proposal WHERE id=?", (graph_id,)).fetchone()
            if not graph or db.execute("SELECT 1 FROM policy_publication WHERE id=?", (graph_id,)).fetchone():
                raise GraphConflict("GRAPH_UNAVAILABLE_OR_PUBLISHED")
            proposal = GraphProposal.model_validate_json(graph[0])
            if verdict.reviewer == proposal.author:
                raise GraphConflict("AUTHOR_CANNOT_REVIEW")
            if verdict.target not in {r.id for r in (*proposal.nodes, *proposal.edges)}:
                raise GraphConflict("REVIEW_TARGET_UNAVAILABLE")
            revision = db.execute("SELECT COALESCE(MAX(revision),0) FROM policy_review WHERE graph_id=?", (graph_id,)).fetchone()[0]
            if type(expected_revision) is not int or expected_revision != revision:
                raise GraphConflict("REVIEW_REVISION_CHANGED")
            db.execute("INSERT INTO policy_review VALUES(?,?,?)", (graph_id, revision+1, verdict.model_dump_json()))
        return revision+1

    def publish(self, graph_id, manifest, *, expected_revision):
        # Caller validates original sources and topology before this transaction.
        # CAS pins the complete verdict history used by that validation.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            revision = db.execute("SELECT COALESCE(MAX(revision),0) FROM policy_review WHERE graph_id=?", (graph_id,)).fetchone()[0]
            if revision != expected_revision:
                raise GraphConflict("REVIEW_REVISION_CHANGED")
            try:
                db.execute("INSERT INTO policy_publication VALUES(?,?)", (graph_id, json.dumps(manifest, sort_keys=True)))
            except sqlite3.IntegrityError:
                raise GraphConflict("GRAPH_UNAVAILABLE_OR_PUBLISHED") from None

    def publication(self, graph_id):
        with self.connect() as db:
            row = db.execute("SELECT manifest FROM policy_publication WHERE id=?", (graph_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def list_ids(self):
        with self.connect() as db:
            return [row[0] for row in db.execute("SELECT id FROM policy_proposal ORDER BY rowid DESC LIMIT 50")]
