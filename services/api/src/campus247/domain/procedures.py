"""F5: procedure playbooks (data), field validation, verbatim check of model-extracted values, run state machine. Pure."""
from __future__ import annotations

import re
import tomllib
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

STATES = ("STARTED", "COLLECTING", "BLOCKED", "READY_FOR_PREVIEW", "PREVIEWED", "SUBMITTED", "CANCELLED", "EXPIRED")
TERMINAL = frozenset({"SUBMITTED", "CANCELLED", "EXPIRED"})
EDITABLE = frozenset({"STARTED", "COLLECTING", "BLOCKED", "READY_FOR_PREVIEW", "PREVIEWED"})
TRANSITIONS = {
    "STARTED": {"COLLECTING", "BLOCKED", "READY_FOR_PREVIEW", "CANCELLED", "EXPIRED"},
    "COLLECTING": {"COLLECTING", "BLOCKED", "READY_FOR_PREVIEW", "CANCELLED", "EXPIRED"},
    "BLOCKED": {"COLLECTING", "BLOCKED", "READY_FOR_PREVIEW", "CANCELLED", "EXPIRED"},
    "READY_FOR_PREVIEW": {"COLLECTING", "BLOCKED", "READY_FOR_PREVIEW", "PREVIEWED", "CANCELLED", "EXPIRED"},
    "PREVIEWED": {"COLLECTING", "BLOCKED", "READY_FOR_PREVIEW", "PREVIEWED", "SUBMITTED", "CANCELLED", "EXPIRED"},
    "SUBMITTED": set(), "CANCELLED": set(), "EXPIRED": set(),
}
FIELD_TYPES = frozenset({"string", "text", "integer", "enum", "date"})
OPS = {"=": lambda a, b: a == b, "!=": lambda a, b: a != b, ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, "<": lambda a, b: a < b}


class StateError(Exception):
    pass


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    type: str
    required: bool = False
    extract: bool = False
    pattern: str | None = None
    values: tuple[str, ...] = ()
    min: int | None = None
    max: int | None = None
    default: object = None


@dataclass(frozen=True)
class Check:
    id: str
    when: dict
    require: dict
    message: str
    source: dict


@dataclass(frozen=True)
class Procedure:
    id: str
    version: int
    title: str
    service_kind: str
    description: str
    fields: tuple[Field, ...]
    checks: tuple[Check, ...] = ()
    sources: tuple[str, ...] = ()
    title_template: str = ""
    summary_fields: tuple[str, ...] = ()

    def field(self, key: str) -> Field | None:
        return next((f for f in self.fields if f.key == key), None)

    def catalog(self) -> dict:
        return {"id": self.id, "title": self.title, "description": self.description,
                "fields": [{"key": f.key, "label": f.label, "type": f.type, "required": f.required, "values": list(f.values), "min": f.min, "max": f.max} for f in self.fields],
                "sources": list(self.sources)}


def load_procedures(directory: Path, *, service_kinds: set[str] | None = None, unit_text: Callable[[str], str | None] | None = None) -> dict[str, Procedure]:
    out: dict[str, Procedure] = {}
    for path in sorted(Path(directory).glob("*.toml")):
        d = tomllib.loads(path.read_text(encoding="utf-8"))
        pid = d["id"]
        if pid in out:
            raise ValueError(f"duplicate procedure {pid}")
        if service_kinds is not None and d["service_kind"] not in service_kinds:
            raise ValueError(f"{pid}: unknown service_kind")
        fields = []
        for f in d.get("fields", []):
            if f["type"] not in FIELD_TYPES:
                raise ValueError(f"{pid}.{f['key']}: bad type")
            if f.get("pattern"):
                re.compile(f["pattern"])
            fields.append(Field(f["key"], f["label"], f["type"], f.get("required", False), f.get("extract", False), f.get("pattern"),
                tuple(f.get("values", ())), f.get("min"), f.get("max"), f.get("default")))
        keys = [f.key for f in fields]
        if len(set(keys)) != len(keys):
            raise ValueError(f"{pid}: duplicate field key")
        checks = []
        for c in d.get("checks", []):
            if c["when"]["field"] not in keys or c["require"]["field"] not in keys or c["when"]["op"] not in OPS or c["require"]["op"] not in OPS:
                raise ValueError(f"{pid}.{c['id']}: check refers to an unknown field or operator")
            if unit_text is not None:
                text = unit_text(c["source"]["unit_id"])
                if text is None or " ".join(c["source"]["quote"].split()) not in " ".join(text.split()):
                    raise ValueError(f"{pid}.{c['id']}: quote is not verbatim in its unit")
            checks.append(Check(c["id"], c["when"], c["require"], c["message"], c["source"]))
        if unit_text is not None:
            for uid in d.get("sources", []):
                if unit_text(uid) is None:
                    raise ValueError(f"{pid}: unknown source unit {uid}")
        t = d.get("ticket", {})
        out[pid] = Procedure(pid, d["version"], d["title"], d["service_kind"], d.get("description", ""), tuple(fields), tuple(checks),
            tuple(d.get("sources", ())), t.get("title_template", d["title"]), tuple(t.get("summary_fields", keys)))
    return out


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold()).replace("đ", "d")
    return " ".join("".join(c for c in text if unicodedata.category(c) != "Mn").split())


def validate_field(f: Field, raw) -> tuple[object, str | None]:
    """-> (clean value, error code or None)."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None, "REQUIRED" if f.required else None
    if f.type == "integer":
        if isinstance(raw, bool) or not isinstance(raw, (int, str)):
            return None, "TYPE_MISMATCH"
        try:
            v = int(raw)
        except ValueError:
            return None, "TYPE_MISMATCH"
        if (f.min is not None and v < f.min) or (f.max is not None and v > f.max):
            return None, "OUT_OF_RANGE"
        return v, None
    if not isinstance(raw, str):
        return None, "TYPE_MISMATCH"
    v = raw.strip()
    if f.type == "enum":
        return (v, None) if v in f.values else (None, "NOT_IN_VALUES")
    if f.type == "date":
        try:
            date.fromisoformat(v)
        except ValueError:
            return None, "BAD_DATE"
        return v, None
    if f.min is not None and len(v) < f.min:
        return None, "TOO_SHORT"
    if f.max is not None and len(v) > f.max:
        return None, "TOO_LONG"
    if f.pattern and not re.fullmatch(f.pattern, v):
        return None, "BAD_FORMAT"
    return v, None


def validate_fields(proc: Procedure, raw: dict) -> tuple[dict, list[dict]]:
    clean, errors = {}, []
    for key in raw:
        if proc.field(key) is None:
            errors.append({"field": key, "code": "UNKNOWN_FIELD"})
    for f in proc.fields:
        if f.key in raw:
            v, err = validate_field(f, raw[f.key])
            if err:
                errors.append({"field": f.key, "code": err})
            elif v is not None:
                clean[f.key] = v
    return clean, errors


def missing_required(proc: Procedure, values: dict) -> list[str]:
    return [f.key for f in proc.fields if f.required and f.key not in values and f.default is None]


def with_defaults(proc: Procedure, values: dict) -> dict:
    return {**{f.key: f.default for f in proc.fields if f.default is not None}, **values}


def run_checks(proc: Procedure, values: dict) -> list[dict]:
    """A check blocks only when its condition is known to hold and the requirement is known to fail; unknown means ask, never guess."""
    blocked = []
    for c in proc.checks:
        w, r = c.when, c.require
        if w["field"] not in values or r["field"] not in values:
            continue
        if OPS[w["op"]](values[w["field"]], w["value"]) and not OPS[r["op"]](values[r["field"]], r["value"]):
            blocked.append({"check": c.id, "message": c.message, "source": c.source})
    return blocked


def verbatim_extraction(text: str, proposed: dict, proc: Procedure) -> tuple[dict, list[dict]]:
    """Keep only extractable fields whose value appears verbatim (after folding) in the student's sentence; others are dropped."""
    folded = _fold(text)
    kept, dropped = {}, []
    for key, value in proposed.items():
        f = proc.field(key)
        if f is None or not f.extract:
            dropped.append({"field": key, "code": "NOT_EXTRACTABLE"})
            continue
        if not isinstance(value, str) or not value.strip() or _fold(value) not in folded:
            dropped.append({"field": key, "code": "NOT_IN_TEXT"})
            continue
        v, err = validate_field(f, value)
        if err:
            dropped.append({"field": key, "code": err})
        else:
            start = folded.find(_fold(value))
            kept[key] = {"value": v, "span": [start, start + len(_fold(value))]}
    return kept, dropped


def advance(state: str, target: str) -> str:
    if target not in TRANSITIONS.get(state, set()):
        raise StateError(f"{state} -> {target}")
    return target


def decide_state(proc: Procedure, values: dict) -> tuple[str, list[dict]]:
    """Where a run stands for the given field values: BLOCKED / COLLECTING / READY_FOR_PREVIEW."""
    blocked = run_checks(proc, values)
    if blocked:
        return "BLOCKED", blocked
    return ("COLLECTING" if missing_required(proc, with_defaults(proc, values)) else "READY_FOR_PREVIEW"), []


def render_ticket(proc: Procedure, values: dict) -> dict:
    vals = with_defaults(proc, values)
    safe = {k: str(v) for k, v in vals.items()}
    title = proc.title_template.format_map(_Safe(safe))[:150]
    lines = [f"{proc.field(k).label}: {vals[k]}" for k in proc.summary_fields if k in vals and proc.field(k)]
    summary = "\n".join(lines) or proc.title
    if len(summary) < 10:
        summary = summary + " — " + proc.title
    return {"service_kind": proc.service_kind, "title": title, "summary": summary[:4000], "fields": {k: str(v)[:500] for k, v in vals.items()}}


class _Safe(dict):
    def __missing__(self, key):
        return ""
