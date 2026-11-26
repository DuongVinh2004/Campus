"""Rule language: ALL/ANY/NOT/PRED tree with per-predicate sources. Structure + verbatim checks."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Callable

from campus247.domain.policy_rules.variables import Vocabulary

OPS = frozenset({"<", "<=", ">", ">=", "=", "!=", "in", "not_in", "between"})
EFFECTS = frozenset({"OVERRIDE_SATISFIED", "OVERRIDE_NOT_SATISFIED", "DEFER_TO_STAFF"})
MAX_DEPTH = 6
MAX_PREDICATES = 40


def canonical_sha256(body: dict) -> str:
    clone = {k: v for k, v in body.items() if k not in {"content_sha256", "status"}}
    return hashlib.sha256(json.dumps(clone, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode()).hexdigest()


def quote_span_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold()).replace("đ", "d")
    return " ".join("".join(c for c in text if unicodedata.category(c) != "Mn").split())


_DIGITS = {"khong": 0, "mot": 1, "hai": 2, "ba": 3, "bon": 4, "tu": 4, "nam": 5, "lam": 5, "sau": 6,
    "bay": 7, "tam": 8, "chin": 9}


def _word_numbers(folded: str) -> set[int]:
    """Numbers 0..100 written in Vietnamese words found inside a folded text."""
    found: set[int] = set()
    words = folded.split()
    for i in range(len(words)):
        for n in range(1, 5):
            chunk = words[i:i + n]
            val = _parse_words(chunk)
            if val is not None:
                found.add(val)
    return found


def _parse_words(chunk: list[str]) -> int | None:
    if not chunk:
        return None
    if chunk == ["mot", "tram"]:
        return 100
    if len(chunk) == 1:
        w = chunk[0]
        if w in _DIGITS and w not in {"tu", "lam"}:
            return _DIGITS[w]
        if w == "muoi":
            return 10
        return None
    if chunk[0] == "muoi" and len(chunk) == 2 and chunk[1] in _DIGITS:
        return 10 + _DIGITS[chunk[1]]
    if len(chunk) >= 2 and chunk[0] in _DIGITS and chunk[1] in {"muoi", "chuc"}:
        tens = _DIGITS[chunk[0]] * 10
        if len(chunk) == 2:
            return tens
        if len(chunk) == 3 and chunk[2] in _DIGITS:
            return tens + _DIGITS[chunk[2]]
    return None


def _number_forms(value) -> list[str]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return []
    forms = []
    if f == int(f):
        forms.append(str(int(f)))
    forms.append(("%g" % f))
    forms.append(("%g" % f).replace(".", ","))
    return list(dict.fromkeys(forms))


def value_in_quote(value, quote: str) -> bool:
    """Is the numeric/string constant present verbatim (digits, comma/dot, or Vietnamese words)?"""
    folded = _fold(quote)
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        for form in _number_forms(value):
            if re.search(r"(?<![0-9.,])" + re.escape(form) + r"(?![0-9])", folded):
                return True
        if float(value) == int(float(value)) and int(float(value)) in _word_numbers(folded):
            return True
        return False
    if isinstance(value, str):
        return _fold(value) in folded
    return False


@dataclass(frozen=True)
class Source:
    unit_id: str
    version_id: str
    path: str
    quote: str

    @staticmethod
    def parse(raw) -> "Source | None":
        if not isinstance(raw, dict):
            return None
        keys = ("unit_id", "version_id", "path", "quote")
        if not all(isinstance(raw.get(k), str) and raw.get(k) for k in keys):
            return None
        return Source(**{k: raw[k] for k in keys})

    def public(self) -> dict:
        return {"unit_id": self.unit_id, "version_id": self.version_id, "path": self.path, "quote": self.quote}


def walk_nodes(node: dict, depth: int = 1):
    yield node, depth
    for key in ("all", "any"):
        for child in node.get(key) or ():
            yield from walk_nodes(child, depth + 1)
    if "not" in node and isinstance(node["not"], dict):
        yield from walk_nodes(node["not"], depth + 1)


def predicates(node: dict):
    return [n for n, _ in walk_nodes(node) if "pred" in n]


def structural_issues(body: dict, vocab: Vocabulary) -> list[dict]:
    issues: list[dict] = []

    def issue(code, target=None, **extra):
        issues.append({"code": code, "target": target, **extra})

    if not isinstance(body.get("rule_id"), str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,80}", body["rule_id"]):
        issue("BAD_RULE_ID")
    if not isinstance(body.get("topic"), str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,60}", body["topic"]):
        issue("BAD_TOPIC")
    concl = body.get("conclusion")
    if not isinstance(concl, dict) or not concl.get("code") or not concl.get("label"):
        issue("BAD_CONCLUSION")
    elif Source.parse(concl.get("source")) is None:
        issue("CONCLUSION_SOURCE_MISSING")
    when = body.get("when")
    if not isinstance(when, dict):
        issue("MISSING_WHEN")
        return issues
    ids: set[str] = set()
    count = 0
    for node, depth in walk_nodes(when):
        nid = node.get("id")
        if not isinstance(nid, str) or not nid or nid in ids:
            issue("BAD_OR_DUPLICATE_NODE_ID", nid)
        ids.add(str(nid))
        if depth > MAX_DEPTH:
            issue("TOO_DEEP", nid)
        kinds = [k for k in ("all", "any", "not", "pred") if k in node]
        if len(kinds) != 1:
            issue("BAD_NODE_KIND", nid)
            continue
        kind = kinds[0]
        if kind in {"all", "any"} and (not isinstance(node[kind], list) or not node[kind]):
            issue("EMPTY_GROUP", nid)
        if kind != "pred":
            continue
        count += 1
        p = node["pred"]
        var = vocab.get(p.get("var")) if isinstance(p, dict) else None
        if var is None:
            issue("UNKNOWN_VARIABLE", nid)
            continue
        op = p.get("op")
        if op not in OPS:
            issue("BAD_OPERATOR", nid)
            continue
        if var.numeric:
            if op in {"in", "not_in"} or op == "between" and not (isinstance(p.get("value"), list) and len(p["value"]) == 2):
                issue("BAD_VALUE", nid)
            elif op not in {"between"} and (isinstance(p.get("value"), bool) or not isinstance(p.get("value"), (int, float))):
                issue("BAD_VALUE", nid)
        elif var.type in {"enum", "string", "boolean"}:
            if op not in {"=", "!=", "in", "not_in"}:
                issue("BAD_OPERATOR_FOR_TYPE", nid)
            if op in {"in", "not_in"} and not isinstance(p.get("value"), list):
                issue("BAD_VALUE", nid)
            if var.type == "enum":
                vals = p["value"] if isinstance(p.get("value"), list) else [p.get("value")]
                if any(v not in var.values for v in vals):
                    issue("ENUM_VALUE_UNKNOWN", nid)
        if var.unit and p.get("unit") != var.unit:
            issue("UNIT_MISMATCH", nid)
        if Source.parse(node.get("source")) is None:
            issue("PREDICATE_SOURCE_MISSING", nid)
    if count > MAX_PREDICATES:
        issue("TOO_MANY_PREDICATES")
    if count == 0:
        issue("NO_PREDICATES")
    for ex in body.get("exceptions") or ():
        if ex.get("effect") not in EFFECTS or not ex.get("rule_id") or Source.parse(ex.get("source")) is None:
            issue("BAD_EXCEPTION", ex.get("rule_id") if isinstance(ex, dict) else None)
    applies = body.get("applies") or {}
    if not applies.get("audiences"):
        issue("MISSING_AUDIENCES")
    return issues


def verbatim_issues(body: dict, text_of_unit: Callable[[str], str | None]) -> list[dict]:
    """Every quote is a verbatim substring of the unit's text; every constant appears in its quote."""
    issues: list[dict] = []

    def check(src_raw, target, value_check=None):
        src = Source.parse(src_raw)
        if src is None:
            return
        text = text_of_unit(src.unit_id)
        if text is None:
            issues.append({"code": "UNIT_NOT_FOUND", "target": target})
        elif src.quote not in text:
            issues.append({"code": "QUOTE_NOT_VERBATIM", "target": target})
        if value_check is not None and not value_check(src.quote):
            issues.append({"code": "VALUE_NOT_IN_QUOTE", "target": target})

    if isinstance(body.get("conclusion"), dict):
        check(body["conclusion"].get("source"), "conclusion")
    for node in predicates(body.get("when") or {}):
        p = node["pred"]
        val = p.get("value")
        vals = val if isinstance(val, list) else [val]
        numeric = [v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]

        def vc(q, numeric=numeric):
            return all(value_in_quote(v, q) for v in numeric)
        check(node.get("source"), node.get("id"), vc if numeric else None)
    for ex in body.get("exceptions") or ():
        check(ex.get("source"), ex.get("rule_id"))
    return issues


def source_hashes(body: dict, text_of_unit: Callable[[str], str | None]) -> dict[str, str]:
    """unit_id -> sha256(text) for every unit the rule cites (used for STALE detection)."""
    out: dict[str, str] = {}
    srcs = []
    if isinstance(body.get("conclusion"), dict):
        srcs.append(body["conclusion"].get("source"))
    srcs += [n.get("source") for n in predicates(body.get("when") or {})]
    srcs += [e.get("source") for e in body.get("exceptions") or ()]
    for raw in srcs:
        src = Source.parse(raw)
        if src is None:
            continue
        text = text_of_unit(src.unit_id)
        if text is not None:
            out[src.unit_id] = quote_span_hash(text)
    return out
