"""F3: per-release unit snapshots, diff between two releases, dependency list, fact conflicts. No user data."""
from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
from typing import Callable, Iterable

from campus247.domain.policy_impact.conflicts import find_fact_conflicts
from campus247.domain.policy_impact.diff import Unit, diff_releases, summarize
from campus247.ports.campus_ops import OpsError

MAX_ITEMS = 500
KEEP_RELEASES = 20
_SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


class SnapshotStore:
    """`<dir>/<release_id>.jsonl.gz` written atomically (tmp, fsync, rename)."""

    def __init__(self, directory: Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, release_id: str) -> Path:
        if not release_id or any(c in release_id for c in "/\\.:"):
            raise ValueError("bad release id")
        return self.dir / f"{release_id}.jsonl.gz"

    def has(self, release_id: str) -> bool:
        return self._path(release_id).is_file()

    def save(self, release_id: str, rows: Iterable[dict]) -> int:
        target = self._path(release_id)
        tmp = target.with_suffix(".tmp")
        n = 0
        with open(tmp, "wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb") as gz:
                for row in rows:
                    gz.write((json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
                    n += 1
            raw.flush()
            os.fsync(raw.fileno())
        os.replace(tmp, target)
        return n

    def load(self, release_id: str) -> list[Unit]:
        with gzip.open(self._path(release_id), "rt", encoding="utf-8") as fh:
            return [Unit.from_row(json.loads(line)) for line in fh]

    def releases(self) -> list[str]:
        files = sorted(self.dir.glob("*.jsonl.gz"), key=lambda p: p.stat().st_mtime)
        return [p.name[: -len(".jsonl.gz")] for p in files]

    def prune(self, keep: int = KEEP_RELEASES, protected: Iterable[str] = ()) -> list[str]:
        protected = set(protected)
        ids = self.releases()
        drop = [r for r in ids[:-keep] if r not in protected] if len(ids) > keep else []
        for r in drop:
            self._path(r).unlink(missing_ok=True)
        return drop


class ImpactService:
    def __init__(self, snapshots: SnapshotStore, current_rows: Callable[[], Iterable[dict]], current_release: Callable[[], str | None],
                 *, report_dir: Path, rules_citing: Callable[[set[str]], list[dict]] | None = None, eval_dir: Path | None = None,
                 facts: Callable[[], list[dict]] | None = None):
        self.snapshots, self.current_rows, self.current_release = snapshots, current_rows, current_release
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.rules_citing = rules_citing or (lambda ids: [])
        self.eval_dir, self.facts = eval_dir, facts or (lambda: [])

    def snapshot_current(self) -> dict:
        release = self.current_release()
        if not release:
            raise OpsError(409, "IMPACT_NO_RELEASE", "Chưa có release đang chạy.")
        if self.snapshots.has(release):
            return {"release_id": release, "created": False}
        rows = ({k: r.get(k) for k in ("unit_id", "document_id", "version_id", "doc_family", "doc_title", "path", "text", "scope",
                                        "effective_from", "effective_until")} for r in self.current_rows())
        n = self.snapshots.save(release, rows)
        return {"release_id": release, "created": True, "units": n}

    def _eval_cases(self, changed: set[str]) -> list[dict]:
        out = []
        if not self.eval_dir or not Path(self.eval_dir).is_dir():
            return out
        for path in sorted(Path(self.eval_dir).rglob("*.jsonl")):
            try:
                for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
                    if not line.strip():
                        continue
                    case = json.loads(line)
                    gold = set(case.get("gold_unit_ids") or ()) | set(case.get("gold_chunk_ids") or ())
                    if gold & changed:
                        out.append({"file": path.name, "line": i + 1, "case_id": case.get("id") or case.get("case_id")})
            except (OSError, ValueError):
                continue
        return out

    def analyze(self, old_release: str | None, new_release: str | None = None) -> dict:
        new_release = new_release or self.current_release()
        if not new_release or not self.snapshots.has(new_release):
            raise OpsError(404, "IMPACT_SNAPSHOT_MISSING", "Chưa có ảnh chụp của release mới.")
        if not old_release or not self.snapshots.has(old_release):
            report = {"old_release": old_release, "new_release": new_release, "status": "BASELINE_ONLY", "summary": {}, "items": [], "dependencies": {}}
            self._save(report)
            return report
        changes = diff_releases(self.snapshots.load(old_release), self.snapshots.load(new_release))
        changed = [c for c in changes if c.status != "UNCHANGED"]
        items = sorted(changed, key=lambda c: (_SEVERITY_ORDER[c.severity], c.status, (c.new or c.old).path))
        touched = {u.unit_id for c in changed if c.severity != "LOW" for u in (c.old,) if u}
        rules = self.rules_citing(touched) if touched else []
        report = {"old_release": old_release, "new_release": new_release, "status": "ANALYZED", "summary": summarize(changes),
            "truncated": len(items) > MAX_ITEMS, "items": [c.public() for c in items[:MAX_ITEMS]],
            "dependencies": {"rules": rules, "eval_cases": self._eval_cases(touched)}}
        self._save(report)
        return report

    def _save(self, report: dict) -> None:
        target = self.report_dir / f"impact-{report['new_release']}.json"
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, target)

    def report(self, release_id: str | None = None) -> dict:
        release_id = release_id or self.current_release()
        path = self.report_dir / f"impact-{release_id}.json"
        if not release_id or not path.is_file():
            raise OpsError(404, "IMPACT_REPORT_MISSING", "Chưa có báo cáo tác động cho release này.")
        return json.loads(path.read_text(encoding="utf-8"))

    def releases(self) -> dict:
        return {"releases": self.snapshots.releases(), "current": self.current_release()}

    def conflicts(self, validity: dict | None = None) -> dict:
        found = find_fact_conflicts(self.facts(), validity)
        return {"count": len(found), "items": found[:200]}

    def on_new_release(self) -> dict:
        """Snapshot the running release and analyse it against the previous snapshot."""
        before = [r for r in self.snapshots.releases()]
        snap = self.snapshot_current()
        previous = [r for r in before if r != snap["release_id"]]
        report = self.analyze(previous[-1] if previous else None, snap["release_id"])
        protected = {r for r in (report.get("old_release"), report["new_release"]) if r}
        self.snapshots.prune(protected=protected)
        return {"snapshot": snap, "status": report["status"], "summary": report.get("summary", {})}
