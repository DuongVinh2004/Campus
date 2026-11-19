"""Closed-world material-claim checks, independent of document extraction code.

Gold is authored from source witnesses, never inferred from the candidate answer.
This is a deterministic check of material fields, not a semantic judge for prose.
Existing source/auth/release checks must still run separately.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal


def fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold().replace("đ", "d"))
    return " ".join("".join(c for c in value if not unicodedata.combining(c)).split())


UNITS = {"tc": "credit", "tin chi": "credit", "%": "percent", "dong": "vnd",
         "vnd": "vnd", "gio": "hour", "tuan": "week", "hoc ky": "semester"}
QUANTITY = re.compile(r"(?<![\w.,])([0-9]+(?:[.,][0-9]+)*)\s*(tin chi|tc\b|%|dong\b|vnd\b|gio\b|tuan\b|hoc ky\b)")
CODE = re.compile(r"(?<![\w])\d{6,7}(?![\w])")
COURSE_CREDIT = re.compile(r"(?<!\d)(\d{6,7})\s*[-–—]\s*(\d{1,2})(?![\d>])")
EDGE = re.compile(r"(?<!\d)(\d{6,7})\s*(?:[-–—:]\s*)?(→|->|↔|<->)\s*(\d{6,7})(?!\d)")
WRITTEN_EDGE = re.compile(r"(?<!\d)(\d{6,7})\s+(?:la\s+)?(tien quyet|hoc truoc|song hanh)(?:\s+cua)?\s+(\d{6,7})(?!\d)")


def number(value: str) -> str:
    # Vietnamese thousands separators and decimal comma; gold uses the same source convention.
    if value.count(".") >= 1 and all(len(p) == 3 for p in value.split(".")[1:]):
        value = value.replace(".", "")
    return str(Decimal(value.replace(",", ".")).normalize())


def quantities(text: str) -> frozenset[tuple[str, str]]:
    return frozenset((number(n), UNITS[u]) for n, u in QUANTITY.findall(fold(text)))


def edges(text: str) -> frozenset[tuple[str, str, str]]:
    found = set()
    for a, arrow, b in EDGE.findall(text):
        found.add(("directed" if arrow in {"→", "->"} else "corequisite", *sorted((a, b)))
                  if arrow in {"↔", "<->"} else ("directed", a, b))
    for a, kind, b in WRITTEN_EDGE.findall(fold(text)):
        found.add(("corequisite", *sorted((a, b))) if kind == "song hanh" else (kind, a, b))
    return frozenset(found)


@dataclass(frozen=True)
class Expectation:
    status: str
    witness: str
    required_terms: tuple[str, ...] = ()
    # Each disjunction is mandatory; this keeps exception/negation checks explicit.
    required_conditions: tuple[tuple[str, ...], ...] = ()
    forbidden_terms: tuple[str, ...] = ()
    expected_codes: frozenset[str] | None = None
    expected_quantities: frozenset[tuple[str, str]] | None = None
    expected_edges: frozenset[tuple[str, str, str]] | None = None
    expected_course_credits: frozenset[tuple[str, str]] | None = None
    witness_binding: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.status not in {"answered", "abstained", "clarification_needed"}:
            raise ValueError("Explicit expected disposition required")
        if self.status == "answered" and (not self.witness.strip() or not self.witness_binding):
            raise ValueError("Answered gold requires an independently checked source witness/binding")


def assess_material(final: dict, gold: Expectation) -> dict:
    text = final.get("content", "")
    body = fold(text)
    failures = []
    status = final.get("status")
    if status != gold.status:
        failures.append("disposition_mismatch")
    if gold.status != "answered":
        if final.get("citations"):
            failures.append("unexpected_citations")
        if any(fold(t) not in body for t in gold.required_terms):
            failures.append("missing_disposition_explanation")
    else:
        missing = [t for t in gold.required_terms if fold(t) not in body]
        if missing:
            failures.append({"missing_terms": missing})
        missing_conditions = [list(group) for group in gold.required_conditions if not any(fold(t) in body for t in group)]
        if missing_conditions:
            failures.append({"missing_conditions": missing_conditions})
        forbidden = [t for t in gold.forbidden_terms if fold(t) in body]
        if forbidden:
            failures.append({"contradicted_conditions": forbidden})
        comparisons = (
            ("course_codes", frozenset(CODE.findall(text)), gold.expected_codes, frozenset(CODE.findall(gold.witness))),
            ("quantities", quantities(text), gold.expected_quantities, quantities(gold.witness)),
            ("relations", edges(text), gold.expected_edges, edges(gold.witness)),
            ("course_credits", frozenset(COURSE_CREDIT.findall(text)), gold.expected_course_credits, frozenset(COURSE_CREDIT.findall(gold.witness))),
        )
        for label, actual, required, allowed in comparisons:
            # The witness is the allowed envelope; exact expected sets narrow it when provided.
            supported = required if required is not None else allowed
            extra = actual - supported
            absent = required - actual if required is not None else frozenset()
            if extra:
                failures.append({"unsupported_" + label: sorted(extra)})
            if absent:
                failures.append({"missing_" + label: sorted(absent)})
    passed = not failures
    return {"passed": passed, "failures": failures, "status": status,
            "answered_correctly": passed and status == "answered",
            "correct_abstention": passed and status == "abstained",
            "correct_clarification": passed and status == "clarification_needed",
            "method": "closed-world material fields and explicit conditions v1",
            "free_prose_semantics_verified": False, "source_authorization_verified": False}
