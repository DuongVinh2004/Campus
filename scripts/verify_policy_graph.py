"""Retained real-source traversal/readback verification, zero model/network calls."""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import time
from dataclasses import replace

from build_policy_graph import ROOT, corpus, destination, review_context
from campus247.application.policy_graph.service import PolicyGraphService
from campus247.domain.policy_graph import TraversalBounds, source_fingerprint
from campus247.infrastructure.repositories.sqlite_policy_graph import SQLitePolicyGraphRepository

CASES = (
    ("S5-SOURCE-01", "Xin giấy xác nhận sinh viên theo thủ tục nào?", {"student-certificate", "certificate-clause"}),
    ("S5-SOURCE-02", "Nhận giấy xác nhận tại đâu?", {"certificate-process", "ctct-qlsv"}),
    ("S5-SOURCE-03", "Quy trình xác nhận chọn mẫu nào?", {"certificate-process", "certificate-form"}),
    ("S5-SOURCE-04", "Cựu sinh viên xác nhận ngành đào tạo?", {"alumni-program-certificate", "certificate-clause"}),
    ("S5-SOURCE-05", "Phúc khảo điểm thi cần lệ phí?", {"appeal", "appeal-fee"}),
    ("S5-SOURCE-06", "Phúc khảo hình thức vấn đáp, thực hành?", {"appeal", "appeal-exception"}),
    ("S5-SOURCE-07", "Chuyển ngành cần đủ những điều kiện nào?", {"transfer", "transfer-all", "transfer-condition-1", "transfer-condition-2", "transfer-condition-3", "transfer-condition-4"}),
    ("S5-SOURCE-08", "Xếp loại tốt nghiệp bị giảm hạng?", {"graduation-grade", "grade-reduction", "grade-any"}),
    ("S5-SOURCE-09", "Xếp loại tốt nghiệp do học lại hoặc kỷ luật?", {"grade-any", "grade-repeat", "grade-discipline"}),
)


async def verify(output="source-verification-01.json"):
    start = time.monotonic()
    from multi_agent_live_resources import paid_view, native_view
    before_paid, before_native = paid_view(), native_view()
    store = corpus()
    repo = SQLitePolicyGraphRepository(destination("policy-graph.sqlite3"), workspace=ROOT)
    service = PolicyGraphService(repo, store, graph_id="huce-policy-development-v1",
        index_fingerprint=store.fingerprint, source_fingerprint=source_fingerprint(store.rows))
    context = review_context()
    results = []
    for case_id, query, expected in CASES:
        started = time.monotonic()
        result = await service.traverse(context=context, query=query,
            bounds=TraversalBounds(depth=3, nodes=24, edges=32, source_reads=16))
        ids = {n["id"] for n in result["nodes"]}
        hashes = []
        for row in result["sources"]:
            original = await store.read(row["source_id"], row["document_version_id"], row["chunk_id"], context=context)
            hashes.append(bool(original and row["content_text"] == original.content_text and
                hashlib.sha256(row["content_text"].encode()).hexdigest() == row["quote_span_hash"] == original.content_sha256))
        results.append({"id": case_id, "query": query, "status": "passed" if expected <= ids and all(hashes) else "failed",
            "missing_nodes": sorted(expected-ids), "nodes": sorted(ids), "edge_ids": [e["id"] for e in result["edges"]],
            "source_refs": [{k: r[k] for k in ("source_id", "document_version_id", "chunk_id", "locator", "quote_span_hash")} for r in result["sources"]],
            "original_hash_matches": hashes, "latency_ms": round((time.monotonic()-started)*1000)})
    denied = replace(context, authorized_scope=replace(context.authorized_scope, tenant_id="unauthorized-tenant"))
    result = await service.traverse(context=denied, query="phúc khảo xác nhận chuyển ngành")
    results.append({"id": "S5-SOURCE-10", "status": "passed" if result["sources"] == result["nodes"] == result["edges"] == [] else "failed", "case": "wrong tenant reveals zero graph data"})
    issues = await service.validate(service.graph_id, context)
    after_paid, after_native = paid_view(), native_view()
    report = {"kind": "retained_real_source_readback_not_fresh_live_generation", "graph_snapshot": service.snapshot,
        "cases": results, "failed": sum(r["status"] == "failed" for r in results), "validation_issues": issues,
        "provider_calls_delta": after_paid["calls"]-before_paid["calls"],
        "conservative_provider_cost_delta_usd": str(__import__("decimal").Decimal(after_paid["conservative_charged_usd"])-__import__("decimal").Decimal(before_paid["conservative_charged_usd"])),
        "native_delta": {k: after_native["counts"][k]-before_native["counts"][k] for k in ("http", "inference", "tokens")},
        "paid_before": before_paid, "paid_after": after_paid, "native_before": before_native, "native_after": after_native,
        "elapsed_ms": round((time.monotonic()-start)*1000), "not_verified": ["fresh live graph-assisted answer quality", "LLM extraction quality", "independent human assessment"]}
    with destination(output).open("x", encoding="utf-8") as out:
        json.dump(report, out, ensure_ascii=False, indent=2)
    print(json.dumps({"failed": report["failed"], "issues": issues, "provider_calls_delta": report["provider_calls_delta"],
        "native_delta": report["native_delta"], "cases": [{"id": r["id"], "status": r["status"], "missing": r.get("missing_nodes")} for r in results]}, ensure_ascii=False))
    return 1 if report["failed"] or issues else 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="source-verification-01.json")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(verify(parser.parse_args().output)))
