"""Evaluation reporting cannot silently relabel failures as quality success."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from evaluate_multi_agent_live import selected_cases, should_halt, summary, usage_delta


def test_exact_case_selection_rejects_typo_and_duplicates():
    dataset = {"cases": [{"id": "CERT-DEV-001"}, {"id": "CERT-DEV-002"}]}
    assert selected_cases(dataset, "CERT-DEV-002") == dataset["cases"][1:]
    for only in ("CERT-DEV-099", "CERT-DEV-001,CERT-DEV-001"):
        with pytest.raises(ValueError):
            selected_cases(dataset, only)


def test_real_provenance_and_terminal_success_do_not_imply_correctness():
    report = summary([{"turns": [{"latency_ms": 500, "failure": None,
        "history_readback_equal": True, "sources": [{"hash_matches": True}]}]},
        {"turns": [{"latency_ms": 5000, "failure": "system_error", "sources": []}]}])
    assert report["failed_turns"] == 1 and report["citations_opened"] == 1
    assert report["correctness"] is report["completeness"] is report["citation_entailment"] is None
    assert report["quality_verdict"].startswith("not_verified")


def test_cost_delta_is_decimal_not_invoice_and_native_counts_are_retained():
    paid = {"calls": 10, "input_tokens_charged": 100, "output_tokens_charged": 50,
            "conservative_charged_usd": "1.7546595"}
    after = paid | {"calls": 11, "conservative_charged_usd": "1.7546598"}
    native = {"counts": {"http": 20, "inference": 10, "tokens": 100}}
    delta = usage_delta(paid, after, native, {"counts": {"http": 22, "inference": 11, "tokens": 150}})
    assert delta["conservative_cost_usd"] == "3E-7" and delta["actual_billed_usd"] is None
    assert delta["native"] == {"http": 2, "inference": 1, "tokens": 50}


def test_operational_halt_preserves_failed_rows_and_does_not_treat_refusal_as_failure():
    failed = {"turns": [{"failure": "system_error", "latency_ms": 3000, "sources": []}]}
    refusal = {"turns": [{"failure": None, "latency_ms": 1000, "sources": []}]}
    assert not should_halt([failed, failed])
    assert not should_halt([failed, refusal, failed])
    rows = [refusal, failed, failed, failed]
    assert should_halt(rows) and len(rows) == 4
    report = summary(rows)
    assert report["failed_turns"] == 3 and report["correctness"] is None
