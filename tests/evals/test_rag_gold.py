"""Synthetic contract fixtures only; no production quality or sealed gold data."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("rag_gold", ROOT / "evals/runners/rag_gold.py")
gold_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gold_module)


def fixture():
    # Existing public dev contract sample; never read release sealed data.
    case = json.loads((ROOT / "evals/datasets/grounded-abstention.jsonl").read_text(encoding="utf-8").splitlines()[0])
    case["review"]["status"] = "approved"
    context = {"authorized_scope": {"tenant_id": "HUCE", "campus_id": "HUCE", "actor_id": "synthetic-a",
        "roles": ["STUDENT"], "audiences": ["STUDENT"], "faculty_codes": ["FIT"], "program_codes": ["CS"]},
        "locale": "vi-VN", "effective_at": "2026-10-02T00:00:00Z", "simulation_policy": "ALLOW_LABELED", "trace_id": "a" * 32}
    evidence = {"fixture_ref": case["fixtures"]["knowledge_refs"][0],
        "source_id": "synthetic-source", "document_version_id": "synthetic-v1", "chunk_id": "synthetic-c1",
        "section_path": ["Section 4"], "page_start": 1, "page_end": 1, "quote_span_hash": "sha256:" + "b" * 64}
    catalog = [deepcopy(evidence)]
    contexts = {case["input"]["trusted_context_fixture_ref"]: deepcopy(context)}
    record = {"case": case, "gold": {"domain": "academic_policy", "scenario_family": "registration",
        "paraphrase_family": "registration-deadline", "authorized_context": context,
        "relevant_chunks": [deepcopy(evidence)], "citations": [deepcopy(evidence)], "negative_labels": [],
        "source_snapshot_hash": gold_module.snapshot_hash(catalog)}}
    return record, catalog, contexts


def validate(record, catalog, contexts, *others):
    return gold_module.validate_gold([record, *others], trusted_chunks=catalog, trusted_contexts=contexts)


def test_valid_gold_and_order_independent_snapshot():
    record, catalog, contexts = fixture()
    assert validate(record, catalog, contexts)["case_count"] == 1
    assert gold_module.snapshot_hash(catalog) == gold_module.snapshot_hash(list(reversed(catalog)))


@pytest.mark.parametrize("field", ["authorized_context", "domain", "relevant_chunks", "citations", "source_snapshot_hash"])
def test_required_gold_fields(field):
    record, catalog, contexts = fixture()
    del record["gold"][field]
    with pytest.raises(gold_module.GoldValidationError, match="INVALID_GOLD_SCHEMA"):
        validate(record, catalog, contexts)


@pytest.mark.parametrize("field,value", [("source_id", "missing"), ("document_version_id", "missing"),
    ("chunk_id", "missing"), ("section_path", ["Wrong section"]), ("quote_span_hash", "sha256:" + "c" * 64)])
def test_unresolved_or_forged_citation(field, value):
    record, catalog, contexts = fixture()
    record["gold"]["citations"][0][field] = value
    with pytest.raises(gold_module.GoldValidationError, match="UNRESOLVED_GOLD_CITATION"):
        validate(record, catalog, contexts)


@pytest.mark.parametrize("mutation", ["missing_context", "spoofed_scope", "snapshot", "no_review", "no_evidence", "naive_time"])
def test_trust_and_evidence_fail_closed(mutation):
    record, catalog, contexts = fixture()
    if mutation == "missing_context":
        contexts.clear()
    elif mutation == "spoofed_scope":
        record["gold"]["authorized_context"]["authorized_scope"]["roles"] = ["SYSTEM_ADMIN"]
    elif mutation == "snapshot":
        record["gold"]["source_snapshot_hash"] = "sha256:" + "0" * 64
    elif mutation == "no_review":
        record["case"]["review"]["status"] = "draft"
    elif mutation == "no_evidence":
        record["gold"]["citations"] = []
    else:
        record["gold"]["authorized_context"]["effective_at"] = "2026-10-02T00:00:00"
    with pytest.raises(gold_module.GoldValidationError):
        validate(record, catalog, contexts)


@pytest.mark.parametrize("kind", ["case_id", "query", "scenario", "paraphrase", "version", "no_diacritics"])
def test_duplicates_and_split_leakage(kind):
    record, catalog, contexts = fixture()
    other = deepcopy(record)
    other["case"]["case_id"] = "EVAL-GQA-002"
    if kind == "case_id":
        other["case"]["case_id"] = record["case"]["case_id"]
    elif kind not in {"query", "no_diacritics"}:
        other["case"]["input"]["turns"][0]["content"] = "Mốc cuối để ghi danh môn học trong bản giả lập?"
        other["case"]["split"] = "validation"
        if kind != "scenario":
            other["gold"]["scenario_family"] = "other"
        if kind != "paraphrase":
            other["gold"]["paraphrase_family"] = "other"
    if kind == "no_diacritics":
        other["case"]["input"]["turns"][0]["content"] = gold_module._query(record["case"]["input"]["turns"][0]["content"])
    with pytest.raises(gold_module.GoldValidationError, match="DUPLICATE|SPLIT_LEAKAGE") as error:
        validate(record, catalog, contexts, other)
    assert "Mốc cuối" not in str(error.value)


def test_abstention_requires_negative_label_and_allows_no_relevant_evidence():
    record, catalog, contexts = fixture()
    record["case"]["expected"]["terminal"] = "abstained"
    record["case"]["expected"]["citations"] = {"required": False, "allowed_source_refs": [], "minimum_valid_citations": 0}
    record["gold"]["relevant_chunks"] = record["gold"]["citations"] = []
    with pytest.raises(gold_module.GoldValidationError, match="MISSING_NEGATIVE_LABEL"):
        validate(record, catalog, contexts)
    record["gold"]["negative_labels"] = ["unanswerable"]
    assert validate(record, catalog, contexts)["case_count"] == 1


def test_invalid_catalog_empty_dataset_and_duplicate_json_keys():
    record, catalog, contexts = fixture()
    with pytest.raises(gold_module.GoldValidationError, match="DUPLICATE_TRUSTED"):
        validate(record, catalog + catalog, contexts)
    with pytest.raises(gold_module.GoldValidationError, match="EMPTY_DATASET"):
        gold_module.validate_gold([], trusted_chunks=catalog, trusted_contexts=contexts)
    with pytest.raises(gold_module.GoldValidationError, match="DUPLICATE_JSON_KEY"):
        json.loads('{"case": 1, "case": 2}', object_pairs_hook=gold_module._unique)


@pytest.mark.parametrize("kind", ["context_type", "catalog", "allowlist", "fixture", "critical_reviewers"])
def test_invalid_catalog_and_expectations(kind):
    record, catalog, contexts = fixture()
    if kind == "context_type":
        contexts = []
    elif kind == "catalog":
        del catalog[0]["source_id"]
    elif kind == "allowlist":
        record["case"]["expected"]["citations"]["allowed_source_refs"] = []
    elif kind == "fixture":
        record["case"]["fixtures"]["knowledge_refs"] = []
    else:
        record["case"]["severity"] = "S1"
    with pytest.raises(gold_module.GoldValidationError):
        validate(record, catalog, contexts)


def test_query_duplication_cannot_be_hidden_by_changing_trace_id():
    record, catalog, contexts = fixture()
    other = deepcopy(record)
    other["case"]["case_id"] = "EVAL-GQA-002"
    other["case"]["input"]["trusted_context_fixture_ref"] = "fixture://trusted-context/other"
    other["gold"]["authorized_context"]["trace_id"] = "b" * 32
    contexts["fixture://trusted-context/other"] = deepcopy(other["gold"]["authorized_context"])
    with pytest.raises(gold_module.GoldValidationError, match="DUPLICATE_QUERY"):
        validate(record, catalog, contexts, other)
