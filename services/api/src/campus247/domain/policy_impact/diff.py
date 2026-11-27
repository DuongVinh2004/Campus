"""Deterministic diff of two releases' units: match, classify, grade. No model, no I/O."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

HIGH_FAMILIES = frozenset({"quy_che", "hoc_phi", "so_tay"})


@dataclass(frozen=True)
class Unit:
    unit_id: str
    document_id: str
    version_id: str
    doc_family: str
    doc_title: str
    path: str
    text: str
    scope: dict = field(default_factory=dict, compare=False, hash=False)
    effective_from: str | None = None
    effective_until: str | None = None

    @staticmethod
    def from_row(row: dict) -> "Unit":
        return Unit(row["unit_id"], row["document_id"], row["version_id"], row.get("doc_family") or "khac", row.get("doc_title") or "",
            row["path"], row["text"], row.get("scope") or {}, row.get("effective_from"), row.get("effective_until"))


def fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold()).replace("đ", "d")
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold().replace("_", " ")
    text = re.sub(r"[^\w\s%/.,-]", " ", text)
    text = re.sub(r"(?<!\d)[%/.,-]|[%/.,-](?!\d)", " ", text)
    return " ".join(text.split())


def _plain(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", unicodedata.normalize("NFC", text).casefold()).split())


def normalize_path(path: str) -> str:
    path = re.sub(r" > tr\.\d+", "", path)
    return re.sub(r"[\s.,;:]+", "", fold(path))


_NUM = re.compile(r"(?<![\w.,])\d+(?:[.,  ]\d+)*(?![\w])")
_DATE = re.compile(r"\b\d{1,2}\s*[/.-]\s*\d{1,2}(?:\s*[/.-]\s*\d{2,4})?\b")


def _canon_number(raw: str) -> str:
    raw = raw.replace(" ", "").replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        raw = raw.replace(".", "")
    raw = raw.replace(",", ".")
    if "." in raw:
        raw = raw.rstrip("0").rstrip(".")
    return raw or "0"


def numbers(text: str) -> Counter:
    body = fold(text)
    out = Counter()
    for m in _DATE.finditer(body):
        out["date:" + re.sub(r"\s", "", m.group(0))] += 1
    for m in _NUM.finditer(_DATE.sub(" ", body)):
        out[_canon_number(m.group(0))] += 1
    return out


def dates(text: str) -> Counter:
    return Counter(k for k in numbers(text).elements() if k.startswith("date:"))


_NEG = re.compile(r"\b(?:khong|chua|cam|mien)\b")


def negations(text: str) -> int:
    return len(_NEG.findall(fold(text)))


_SCOPE = re.compile(r"\b(?:khoa|k)\s?(\d{2})\b|\bnganh\s+[a-z ]{3,30}|\bchuong trinh\s+[a-z ]{3,30}|\b(?:cu nhan|ky su|kien truc su|sau dai hoc|thac si|tien si)\b")


def scope_terms(text: str, scope: dict | None = None) -> frozenset:
    terms = {m.group(0).strip() for m in _SCOPE.finditer(" ".join(fold(text).split()))}
    for key, vals in (scope or {}).items():
        for v in vals or ():
            terms.add(f"{key}:{v}")
    return frozenset(terms)


def classify(old: Unit, new: Unit) -> list[str]:
    labels: list[str] = []
    same_text = normalize_text(old.text) == normalize_text(new.text)
    if not same_text:
        if numbers(old.text) != numbers(new.text):
            labels.append("NUMERIC")
        if dates(old.text) != dates(new.text):
            labels.append("DEADLINE")
        if negations(old.text) != negations(new.text):
            labels.append("NEGATION")
    if scope_terms(old.text, old.scope) != scope_terms(new.text, new.scope):
        labels.append("SCOPE")
    if (old.effective_from, old.effective_until) != (new.effective_from, new.effective_until):
        labels.append("EFFECTIVE")
    if not labels:
        labels.append("WORDING_ONLY" if same_text else "TEXT_OTHER")
    return labels


def severity(status: str, labels: list[str], family: str) -> str:
    high_kind = status == "REMOVED" or any(l in {"NUMERIC", "NEGATION", "SCOPE"} for l in labels)
    if high_kind and family in HIGH_FAMILIES:
        return "HIGH"
    if status == "UNCHANGED_TEXT_NEW_EDITION" or labels == ["WORDING_ONLY"]:
        return "LOW"
    return "MEDIUM"


def _grams(text: str, n: int = 3) -> set:
    words = _plain(text).split()
    return {tuple(words[i:i + n]) for i in range(max(len(words) - n + 1, 1))} if words else set()


def jaccard(a: str, b: str) -> float:
    ga, gb = _grams(a), _grams(b)
    return len(ga & gb) / len(ga | gb) if ga and gb else 0.0


def _title_key(title: str) -> str:
    return re.sub(r"\d+", "", fold(title)).strip()


@dataclass
class Change:
    status: str  # UNCHANGED | MODIFIED | MOVED | ADDED | REMOVED | UNCHANGED_TEXT_NEW_EDITION
    old: Unit | None
    new: Unit | None
    labels: list[str] = field(default_factory=list)
    severity: str = "LOW"
    renumbered: bool = False
    similarity: float | None = None

    def public(self) -> dict:
        u = self.new or self.old
        return {"status": self.status, "labels": self.labels, "severity": self.severity, "renumbered": self.renumbered,
                "family": u.doc_family, "path": u.path, "old_unit_id": self.old.unit_id if self.old else None,
                "new_unit_id": self.new.unit_id if self.new else None, "similarity": self.similarity,
                "numeric": numeric_changes(self.old, self.new) if self.old and self.new and "NUMERIC" in self.labels else []}


def numeric_changes(old: Unit, new: Unit) -> list[dict]:
    a, b = numbers(old.text), numbers(new.text)
    removed, added = sorted((a - b).elements()), sorted((b - a).elements())
    return [{"old": o, "new": n} for o, n in zip(removed, added)] + [{"old": o, "new": None} for o in removed[len(added):]] + [
        {"old": None, "new": n} for n in added[len(removed):]]


def diff_releases(old_units: list[Unit], new_units: list[Unit], *, rematch_threshold: float = 0.6) -> list[Change]:
    old_by_id = {u.unit_id: u for u in old_units}
    new_by_id = {u.unit_id: u for u in new_units}
    changes: list[Change] = []
    left_old = {i for i in old_by_id if i not in new_by_id}
    left_new = {i for i in new_by_id if i not in old_by_id}
    for uid in old_by_id.keys() & new_by_id.keys():
        changes.append(Change("UNCHANGED", old_by_id[uid], new_by_id[uid]))

    def finish(old: Unit, new: Unit, renumbered=False, similarity=None, moved=False):
        status = "MOVED" if moved else "MODIFIED"
        labels = classify(old, new)
        changes.append(Change(status, old, new, labels, severity(status, labels, new.doc_family), renumbered, similarity))

    # 2) same document version + same path
    by_key = {}
    for i in left_old:
        by_key.setdefault((old_by_id[i].version_id, normalize_path(old_by_id[i].path)), []).append(i)
    for i in sorted(left_new):
        key = (new_by_id[i].version_id, normalize_path(new_by_id[i].path))
        cands = [c for c in by_key.get(key, []) if c in left_old]
        if cands:
            c = cands[0]
            left_old.discard(c); left_new.discard(i)
            finish(old_by_id[c], new_by_id[i])
    # 3) new edition: same title family + same normalized path
    by_key = {}
    for i in left_old:
        by_key.setdefault((_title_key(old_by_id[i].doc_title), old_by_id[i].doc_family, normalize_path(old_by_id[i].path)), []).append(i)
    for i in sorted(left_new):
        n = new_by_id[i]
        cands = [c for c in by_key.get((_title_key(n.doc_title), n.doc_family, normalize_path(n.path)), []) if c in left_old]
        if cands:
            c = max(cands, key=lambda x: jaccard(old_by_id[x].text, n.text))
            left_old.discard(c); left_new.discard(i)
            o = old_by_id[c]
            if normalize_text(o.text) == normalize_text(n.text) and o.version_id != n.version_id:
                changes.append(Change("UNCHANGED_TEXT_NEW_EDITION", o, n, ["WORDING_ONLY"], "LOW"))
            else:
                finish(o, n)
    # 4) renumbering: greedy Jaccard among leftovers of the same family and depth
    scored = []
    old_list = sorted(left_old)
    for i in sorted(left_new):
        n = new_by_id[i]
        depth = n.path.count(">")
        for c in old_list:
            o = old_by_id[c]
            if o.doc_family != n.doc_family or o.path.count(">") != depth or len(o.text) < 20:
                continue
            s = jaccard(o.text, n.text)
            if s >= rematch_threshold:
                scored.append((s, c, i))
    for s, c, i in sorted(scored, key=lambda t: (-t[0], t[1], t[2])):
        if c in left_old and i in left_new:
            left_old.discard(c); left_new.discard(i)
            same_path = normalize_path(old_by_id[c].path) == normalize_path(new_by_id[i].path)
            finish(old_by_id[c], new_by_id[i], renumbered=not same_path, similarity=round(s, 3), moved=not same_path)
    for c in sorted(left_old):
        o = old_by_id[c]
        changes.append(Change("REMOVED", o, None, [], severity("REMOVED", [], o.doc_family)))
    for i in sorted(left_new):
        n = new_by_id[i]
        changes.append(Change("ADDED", None, n, [], "HIGH" if n.doc_family in HIGH_FAMILIES else "MEDIUM"))
    return changes


def summarize(changes: list[Change]) -> dict:
    status = Counter(c.status for c in changes)
    sev = Counter(c.severity for c in changes if c.status != "UNCHANGED")
    labels = Counter(l for c in changes for l in c.labels)
    return {"by_status": dict(status), "by_severity": dict(sev), "by_label": dict(labels)}
