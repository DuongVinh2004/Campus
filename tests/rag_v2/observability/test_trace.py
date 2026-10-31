import json
import logging

from campus247.rag_v2.observability.trace import TurnTrace, emit


def test_warning_is_one_json_line_with_finite_data_only(caplog):
    trace = TurnTrace(candidate_count=45, rerank_scores=[0.7, -2.5],
                      statement_rejections={0: ("NUMBER_NOT_IN_SOURCE",), 1: ("SEMANTIC_UNSUPPORTED",)},
                      outcome_kind="partial", latency_ms={"retrieval": 8.5, "generation": 25})
    with caplog.at_level(logging.WARNING, logger="campus247.rag_v2"):
        emit(trace)
    assert len(caplog.records) == 1
    record, = caplog.records
    assert record.levelno == logging.WARNING
    assert record.message.startswith("rag_v2_trace ") and "\n" not in record.message
    payload = json.loads(record.message.removeprefix("rag_v2_trace "))
    assert payload["candidate_count"] == 45 and payload["rerank_scores"] == [0.7, -2.5]
    assert payload["outcome_kind"] == "partial"
    assert payload["latency_ms"] == {"retrieval": 8.5, "generation": 25}


def test_pii_unknown_fields_unbounded_lists_and_nonfinite_values_are_excluded(caplog):
    pii = "synthetic-office@huce.edu.vn\n0912345678"
    trace = TurnTrace(candidate_count=-4, rerank_scores=[float("nan"), float("inf")] + [0.5] * 1000,
                      statement_rejections={0: (pii, "UNIT_NOT_CITED"), pii: (pii,)},
                      outcome_kind=pii, latency_ms={pii: 42, "total": float("inf"), "retrieval": -1})
    trace.question = pii
    with caplog.at_level(logging.WARNING, logger="campus247.rag_v2"):
        emit(trace)
    record, = caplog.records
    assert pii not in record.message and "synthetic-office" not in record.message
    payload = json.loads(record.message.removeprefix("rag_v2_trace "))
    assert len(record.message) < 7000 and len(payload["rerank_scores"]) <= 60
    assert payload["statement_rejections"] == [{"i": 0, "reasons": ["UNIT_NOT_CITED"]}]
    assert payload["latency_ms"] == {"retrieval": 0}
    assert payload["outcome_kind"] is None
