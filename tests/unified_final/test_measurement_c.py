"""Evaluation must retain missing/failure evidence instead of inventing metrics."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from scripts.unified_parallel_c_evaluate import distribution, score


def test_missing_observation_is_not_correct_abstention():
    assert not score({"workflow": None}, {})["all_material_checks_passed"]
    assert score({"workflow": None}, {"workflow": None})["all_material_checks_passed"]


def test_boolean_observation_cannot_be_counted_as_integer_http_success():
    assert not score({"http_status": 1}, {"http_status": True})["all_material_checks_passed"]


def test_faster_wrong_recipient_never_passes_material_correctness():
    result = score({"recipient": "fixture-student-A", "http_status": 200},
                   {"recipient": "fixture-student-B", "http_status": 200, "latency_ms": .01})
    assert not result["all_material_checks_passed"] and result["checks"]["http_status"]


def test_unobserved_or_small_sample_cannot_publish_p95():
    assert distribution([])["p95_ms"] is None
    assert distribution([1, 2, 3, 4])["p95_ms"] is None
    assert distribution(list(range(1, 21)))["p95_ms"] == 19
