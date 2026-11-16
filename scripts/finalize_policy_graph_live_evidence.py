"""Append source-reviewed development results; never dispatch or publish a model output."""
import argparse
import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal

from build_policy_graph import ROOT, destination, corpus
from multi_agent_live_resources import paid_view, native_view
from campus247.application.policy_graph.service import structural_issues
from campus247.domain.policy_graph import GraphProposal


# Codex observations after reading each actual answer and its original source.
# These are development review, not an independent human assessment.
NOTES = (
    "Registration, selected service/form, submission and collection location/appointment match handbook39.",
    "Responsible specialist, website/email appointment and CTCT&QLSV floor2 collection match handbook39.",
    "Service/form selection and submission match handbook39; no invented form code/version.",
    "Alumni industry-confirmation service matches handbook35; general student/alumni procedure matches39.",
    "Student portal registration and online bank payment match61; no invented amount/deadline.",
    "Oral/practical exclusion matches the visually inspected retained PDF61 side note.",
    "No invented fee amount. Generic refusal is safe, but does not explicitly identify the missing amount or open a citation.",
    "All four Article15(1) conditions preserved, including year/time, admissions, capacity and both approvals.",
    "Admissions alone is not represented as sufficient: answer retains all four conditions. Direct no would be clearer.",
    "Both unit-head and rector approval preserved together with remaining conditions; no eligibility decision.",
    "Two independent reduction triggers retained for excellent/good grades, strict >5% and discipline >=warning during study.",
    "Explicit one-of wording rejects the proposed conjunction; excellent/good scope and both thresholds retained.",
)


def read(name):
    return json.loads(destination(name).read_text(encoding="utf-8"))


def retain(name, value):
    with destination(name).open("x", encoding="utf-8") as out:
        json.dump(value, out, ensure_ascii=False, indent=2)


def main(output):
    if destination(output).exists():
        raise FileExistsError("retain prior source quality review; choose a new exact report")
    admission = read("live-campaign-admission-01.json")
    after, native_after = paid_view(), native_view()
    cases = []
    for number, note in enumerate(NOTES, 1):
        name = f"live-case-{number:03d}-01.json"
        row = read(name)
        turn = row["turn"]
        if turn["failure"] or not turn["history_readback_equal"] or not row["graph_events"]:
            raise ValueError("operational failure must be inspected before source quality aggregation")
        if any(not s["hash_matches"] for s in turn["sources"]):
            raise ValueError("source integrity failure")
        cases.append({"id": row["case_id"], "artifact": name,
            "artifact_sha256": hashlib.sha256(destination(name).read_bytes()).hexdigest(),
            "correctness": 2, "completeness": 1 if number == 7 else 2,
            "citation_entailment": 2 if turn["sources"] else None,
            "source_hashes_verified": len(turn["sources"]),
            "conditions_and_audience": "source_preserved" if number != 7 else "safe_abstention",
            "temporal": "no_legal_effective_date_invented; legal applicability remains unknown",
            "note": note, "response_class": turn["final"]["response_class"],
            "history_equal": True, "graph_events": row["graph_events"],
            "latency_ms": turn["latency_ms"], "provider_calls": turn["provider_calls"],
            "conservative_cost_usd": turn["conservative_cost_usd"],
            "native": turn["native"], "input_tokens": turn["input_tokens_charged"],
            "output_tokens": turn["output_tokens_charged"]})
    extraction = []
    store = corpus()  # Same retained index, no HTTP/native inference.
    source_rows = {r["chunk_id"]: r for r in store.rows}
    db_path = destination("policy-graph.sqlite3")
    with sqlite3.connect(db_path.as_uri()+"?mode=ro", uri=True) as db:
        for number in (1, 2):
            response = read(f"live-extraction-{number:02d}-01.json")
            if response["http_status"] != 200:
                raise ValueError("failed extraction must remain explicit")
            graph_id = response["result"]["candidate_id"]
            raw = db.execute("SELECT raw FROM policy_proposal WHERE id=?", (graph_id,)).fetchone()[0]
            proposal = GraphProposal.model_validate_json(raw)
            model = db.execute("SELECT raw FROM policy_extraction WHERE request_id=?", (graph_id.removeprefix("candidate-"),)).fetchone()[0]
            source_ok = True
            for record in (*proposal.nodes, *proposal.edges):
                ref = record.source
                original = source_rows.get(ref.chunk_id)
                source_ok = source_ok and bool(original and
                    original["source_id"] == ref.source_id and original["document_version_id"] == ref.document_version_id and
                    original["quote_span_hash"].removeprefix("sha256:") == ref.content_sha256 and
                    ref.quote in original["content_text"])
            publication = db.execute("SELECT manifest FROM policy_publication WHERE id=?", (graph_id,)).fetchone()
            reviews = db.execute("SELECT revision,payload FROM policy_review WHERE graph_id=? ORDER BY revision", (graph_id,)).fetchall()
            extraction.append({"id": graph_id, "nodes": len(proposal.nodes), "edges": len(proposal.edges),
                "raw_model_sha256": hashlib.sha256(model.encode()).hexdigest(), "raw_model_retained": True,
                "source_bindings_verified": source_ok, "structural_issues": structural_issues(proposal),
                "publication": json.loads(publication[0]) if publication else None,
                "reviews": [{"revision": r, **json.loads(v)} for r, v in reviews],
                "usage": response["result"]["usage"], "quality_verdict": "requires_correction_do_not_publish",
                "note": "Document and clause duplicate label, reversed defined_by relation; requires-to-unit semantics need review; no Form node." if number == 1 else
                    "Small fee fragment only; defined_by direction/types need review. STUDENT audience is not evidenced by heading-only span. No Procedure/Form/exception extracted from these narrow inputs."})
    before, native_before = admission["paid_snapshot"], admission["native_snapshot"]
    calls = after["calls"]-before["calls"]
    if calls != sum(c["provider_calls"] for c in cases)+2:
        raise ValueError("unexpected concurrent provider usage")
    if after["call_cap"] != 12192 or after["hard_cap_usd"] != "10" or after["unsettled_attempts_retained"] != before["unsettled_attempts_retained"]:
        raise ValueError("authorization or retained unknown reservations changed")
    latencies = sorted(c["latency_ms"] for c in cases)
    report = {"at": datetime.now(timezone.utc).isoformat(), "kind": "development_Codex_source_review_not_held_out",
        "rubric": {"0": "incorrect/unsupported", "1": "partial", "2": "source-supported and complete for asked scope"},
        "summary": {"questions": len(cases), "system_failures": 0, "grounded_answers": 11, "safe_refusals": 1,
            "correctness_2": 12, "completeness_2": 11, "completeness_1": 1,
            "citation_entailment_2": 11, "citations_verified": sum(c["source_hashes_verified"] for c in cases),
            "history_equal": 12, "graph_queries_with_completed_traversal": 12,
            "latency_p50_ms": latencies[math.ceil(len(latencies)*.5)-1],
            "latency_p95_ms": latencies[math.ceil(len(latencies)*.95)-1],
            "extraction_http_success": 2, "extraction_requiring_correction": 2, "extraction_auto_published": 0},
        "cases": cases, "extraction": extraction,
        "paid_before": before, "paid_after": after, "native_before": native_before, "native_after": native_after,
        "usage": {"provider_calls": calls,
            "input_tokens_charged": after["input_tokens_charged"]-before["input_tokens_charged"],
            "output_tokens_charged": after["output_tokens_charged"]-before["output_tokens_charged"],
            "conservative_cost_usd": str(Decimal(after["conservative_charged_usd"])-Decimal(before["conservative_charged_usd"])),
            "actual_billed_usd": None,
            "native": {k: native_after["counts"][k]-native_before["counts"][k] for k in ("http", "inference", "tokens")}},
        "limitations": ["Development authored set, not independent human assessment/production readiness",
            "Generic safe refusal for missing fee amount needs clearer source-specific explanation",
            "Graph traversal can also expand secondary hybrid anchors; final source/rerank/claims gates remain required",
            "Two narrow extraction samples do not establish ALL/ANY extraction quality",
            "Legal dates and detailed certificate form/version remain unknown",
            "PDF61 was visually checked for this answer review; no OCR/source/publication rewritten"],
        "evidence": {"visual_pdf_page": "source-handbook-page-061-01.png",
            "retained_runtime_readback": "../multi-agent-integrated-20261013-01/stage5-after-live-readback-01.json"}}
    retain(output, report)
    print(json.dumps({"summary": report["summary"], "usage": report["usage"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="live-quality-review-01.json")
    main(parser.parse_args().output)
