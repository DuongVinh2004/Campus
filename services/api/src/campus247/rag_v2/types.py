"""Shared value types of the RAG v2 pipeline. Frozen, no I/O, no framework imports."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping

UnitKind = Literal["article", "clause", "table_row", "handbook_section", "page", "notice", "curriculum_row"]
FactKind = Literal["fee", "deadline", "prerequisite", "contact"]
OutcomeKind = Literal["answer", "partial", "clarify", "refuse", "transient_error"]
RefuseReason = Literal["no_source", "out_of_scope", "unverified", "unsafe"]


@dataclass(frozen=True)
class Scope:
    """Applicability of a unit. Empty tuple = applies to all."""
    cohorts: tuple[str, ...] = ()      # e.g. ("K64", "K65")
    programs: tuple[str, ...] = ()     # e.g. ("7480201",) or normalized names
    academic_years: tuple[str, ...] = ()  # e.g. ("2026-2027",)


@dataclass(frozen=True)
class Unit:
    unit_id: str                 # stable: sha256(version_id|locator|text_sha)[:16]
    chunk_ids: tuple[str, ...]   # source rows in knowledge_chunk this unit was built from
    document_id: str
    version_id: str
    doc_title: str
    doc_family: str
    kind: UnitKind
    path: str                    # human locator, e.g. "Điều 14 > Khoản 1" or "Sổ tay > Mục 3 > tr.27"
    page: int | None
    text: str                    # exact source text of the unit (never paraphrased)
    effective_from: str | None = None
    effective_until: str | None = None
    scope: Scope = Scope()
    parent_unit_id: str | None = None


@dataclass(frozen=True)
class Fact:
    fact_id: str
    kind: FactKind
    subject: str                 # normalized subject, e.g. "học phí tín chỉ đại trà"
    value: str                   # exactly as in source, e.g. "580.500 đồng"
    unit_id: str
    quote: str                   # verbatim substring of Unit.text containing value
    scope: Scope = Scope()
    attributes: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Understanding:
    original: str
    search_query: str            # deterministic normalization (abbreviations, diacritics, year forms)
    topics: tuple[str, ...]
    cohort: str | None
    program: str | None
    academic_year: str | None
    question_type: str           # lookup|procedure|condition|number|deadline|contact|compare|smalltalk|oos|unclear
    required_slots: tuple[str, ...]
    missing_slots: tuple[str, ...]
    clarify_prompt: str | None   # fixed server text with suggestions when we must ask back
    out_of_scope: bool = False


@dataclass(frozen=True)
class Candidate:
    unit_id: str
    lexical_rank: int | None
    vector_rank: int | None
    fused_score: float
    rerank_score: float | None = None
    final_rank: int = 0


@dataclass(frozen=True)
class Statement:
    text: str
    unit_ids: tuple[str, ...]


@dataclass(frozen=True)
class StatementVerdict:
    statement: Statement
    passed: bool
    reasons: tuple[str, ...] = ()    # finite codes: NUMBER_NOT_IN_SOURCE, CODE_NOT_IN_SOURCE, DATE_NOT_IN_SOURCE, NEGATION_MISMATCH, UNIT_NOT_CITED, SEMANTIC_UNSUPPORTED, SCOPE_MISMATCH


@dataclass(frozen=True)
class Citation:
    unit_id: str
    chunk_ids: tuple[str, ...]
    document_id: str
    version_id: str
    doc_title: str
    path: str
    page: int | None
    quote: str


@dataclass(frozen=True)
class Outcome:
    kind: OutcomeKind
    text: str                                  # user-facing Vietnamese text (fixed or built from verified statements)
    statements: tuple[Statement, ...] = ()
    citations: tuple[Citation, ...] = ()
    reason: RefuseReason | None = None
    partial_note: str | None = None
    retry_hint: str | None = None
    suggestions: tuple[str, ...] = ()
    trace: Mapping[str, object] = field(default_factory=dict)  # finite counters/codes only, never question text
