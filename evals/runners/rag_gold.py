"""Offline gold integrity validation, not retrieval or production quality evidence.

The caller supplies trusted context fixtures and an independently resolved index
snapshot. Never construct either catalog from the gold case expectations.
Run all shards together to check split isolation; sealed text is never printed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker


SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"


class GoldValidationError(ValueError):
    """Only safe reason codes; never raw queries, identity or sealed content."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def snapshot_hash(chunks: Sequence[dict[str, Any]]) -> str:
    return "sha256:" + hashlib.sha256(_canonical(sorted(chunks, key=_canonical)).encode()).hexdigest()


def _key(ref: dict[str, Any]) -> tuple[str, str, str]:
    return ref["source_id"], ref["document_version_id"], ref["chunk_id"]


def _query(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    return " ".join(re.findall(r"\w+", "".join(c for c in folded if not unicodedata.combining(c))))


def validate_gold(cases: Sequence[dict[str, Any]], *, trusted_chunks: Sequence[dict[str, Any]],
                  trusted_contexts: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    schema = yaml.safe_load((SCHEMAS / "rag-gold.schema.yaml").read_text(encoding="utf-8"))
    base = yaml.safe_load((SCHEMAS / "eval-case.schema.yaml").read_text(encoding="utf-8"))
    # Bundle the existing canonical schema locally; no remote resolution or new dependency.
    schema["$defs"]["canonical_case"] = base
    schema["properties"]["case"] = {"$ref": "#/$defs/canonical_case"}
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    evidence_validator = Draft202012Validator({"$ref": "#/$defs/evidence", "$defs": schema["$defs"]})
    if not isinstance(trusted_contexts, Mapping):
        raise GoldValidationError("INVALID_CONTEXT_CATALOG")
    if not cases:
        raise GoldValidationError("EMPTY_DATASET")
    catalog = {}
    for ref in trusted_chunks:
        if not evidence_validator.is_valid(ref):
            raise GoldValidationError("INVALID_TRUSTED_EVIDENCE")
        if _key(ref) in catalog:
            raise GoldValidationError("DUPLICATE_TRUSTED_EVIDENCE")
        catalog[_key(ref)] = ref
    snapshot = snapshot_hash(trusted_chunks)
    ids, duplicate_queries, families = set(), set(), {}
    for record in cases:
        if not validator.is_valid(record):
            raise GoldValidationError("INVALID_GOLD_SCHEMA")
        case, gold = record["case"], record["gold"]
        if case["case_id"] in ids:
            raise GoldValidationError("DUPLICATE_CASE_ID")
        ids.add(case["case_id"])
        if case["review"]["status"] != "approved" or not case["review"]["reviewers"]:
            raise GoldValidationError("UNAPPROVED_GOLD")
        fixture = case["input"]["trusted_context_fixture_ref"]
        if not fixture or trusted_contexts.get(fixture) != gold["authorized_context"]:
            raise GoldValidationError("UNRESOLVED_AUTH_CONTEXT")
        if gold["source_snapshot_hash"] != snapshot:
            raise GoldValidationError("SOURCE_SNAPSHOT_MISMATCH")
        turns = case["input"]["turns"]
        if turns[-1]["role"] != "user" or not _query(turns[-1]["content"]):
            raise GoldValidationError("MISSING_QUERY")
        # Include the whole conversation: identical last turns may depend on different history.
        query = tuple((t["role"], _query(t["content"])) for t in turns)
        context_scope = {k: v for k, v in gold["authorized_context"].items() if k != "trace_id"}
        duplicate = (query, _canonical(context_scope))
        if duplicate in duplicate_queries:
            raise GoldValidationError("DUPLICATE_QUERY")
        duplicate_queries.add(duplicate)
        relevant = {_key(ref) for ref in gold["relevant_chunks"]}
        for ref in gold["relevant_chunks"] + gold["citations"]:
            if catalog.get(_key(ref)) != ref:
                raise GoldValidationError("UNRESOLVED_GOLD_CITATION")
            if ref["fixture_ref"] not in case["fixtures"]["knowledge_refs"]:
                raise GoldValidationError("UNRESOLVED_KNOWLEDGE_FIXTURE")
            if ref["page_end"] is not None and (ref["page_start"] is None or ref["page_end"] < ref["page_start"]):
                raise GoldValidationError("INVALID_LOCATOR")
        if any(_key(ref) not in relevant for ref in gold["citations"]):
            raise GoldValidationError("CITATION_NOT_RELEVANT")
        expectation = case["expected"]["citations"]
        if any(ref["fixture_ref"] not in expectation["allowed_source_refs"] for ref in gold["citations"]):
            raise GoldValidationError("CITATION_NOT_ALLOWED")
        if len(gold["citations"]) < expectation["minimum_valid_citations"]:
            raise GoldValidationError("MISSING_GOLD_CITATION")
        if case["expected"]["terminal"] == "answered" and (not relevant or not gold["citations"] or not expectation["required"]):
            raise GoldValidationError("MISSING_ANSWER_EVIDENCE")
        if case["expected"]["terminal"] != "answered" and not gold["negative_labels"]:
            raise GoldValidationError("MISSING_NEGATIVE_LABEL")
        # Reviewed family IDs capture semantic paraphrases without fake embedding similarity.
        # Source versions and normalized queries also cannot cross split boundaries.
        keys = [("query", query), ("scenario", gold["scenario_family"]),
                ("paraphrase", gold["paraphrase_family"])]
        keys += [("version", (ref["source_id"], ref["document_version_id"])) for ref in gold["relevant_chunks"]]
        for key in keys:
            if key in families and families[key] != case["split"]:
                raise GoldValidationError("SPLIT_LEAKAGE")
            families[key] = case["split"]
    return {"status": "validated", "case_count": len(ids), "source_snapshot_hash": snapshot}


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise GoldValidationError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line, object_pairs_hook=_unique) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", nargs="+", type=Path)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--contexts", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = validate_gold([case for path in args.cases for case in _jsonl(path)],
            trusted_chunks=_jsonl(args.catalog),
            trusted_contexts=json.loads(args.contexts.read_text(encoding="utf-8"), object_pairs_hook=_unique))
        print(_canonical(report))
        return 0
    except GoldValidationError as error:
        print(str(error), file=sys.stderr)
    except (ValueError, OSError, TypeError, KeyError):
        print("INVALID_GOLD_INPUT", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
