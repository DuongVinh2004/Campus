"""Bounded measurements of current real BGE and existing live RAG HTTP runtime."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import sys
import time

from certificate_stage1_workspace import ROOT, STATE, checked, retain
sys.path[:0] = [str(ROOT), str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")]

DATASET = ROOT / "evals/datasets/certificate-development-20261013.json"


def paid_snapshot():
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "infra/local/public-rag-20261013").glob("provider-*.json")]
    return max(rows, key=lambda r: (r["snapshot"]["calls"], r.get("stage") == "result"))["snapshot"]


def native_snapshot():
    rows = [json.loads(p.read_text(encoding="utf-8")) for parent in (ROOT / "infra/local").glob("rag-advanced-models-20261013-*")
            for p in parent.glob("native-*-reservation.json")]
    return max(rows, key=lambda r: r["counts"]["inference"])


def percentile(values, p):
    return sorted(values)[max(0, math.ceil(len(values) * p)-1)] if values else None


async def retrieval(dataset):
    from scripts.public_rag_retrieval import load_public_hybrid_store
    from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
    from datetime import datetime, timezone
    store = load_public_hybrid_store(ROOT / "data/huce-public-20261013", tenant_id="huce-local-public", campus_id="HUCE", faq_directory=ROOT / "data/huce-faq-20261013")
    context = RetrievalContext(AuthorizedScope("huce-local-public", "HUCE", "certificate-eval", frozenset({"STUDENT"}), frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})), "vi", datetime.now(timezone.utc), SimulationPolicy.DENY, "1"*32)
    before, paid_before = native_snapshot(), paid_snapshot()
    # Bind expected source_refs to the exact visually reviewed page in the active
    # canonical corpus; raw historical paired-page OCR hashes differ by design.
    source_ids = {}
    for ref, page in (("catalog", 35), ("procedure", 39)):
        matches = [r["chunk_id"] for r in store.rows if r["page_start"] == page
                   and r["canonical_uri"] == dataset["sources"][ref]["url"]]
        if len(matches) != 1:
            raise ValueError("ambiguous source provenance")
        source_ids[ref] = matches[0]
    rows = []
    for case in dataset["cases"]:
        usage = native_snapshot()
        if usage["caps"]["inference"]-usage["counts"]["inference"] < 40 or usage["caps"]["tokens"]-usage["counts"]["tokens"] < 12000:
            rows.append({"id": case["id"], "skipped": "retain native headroom for limited generation/browser checks"})
            continue
        start = time.monotonic()
        try:
            found = await store.search(case["question"], context)
            ids = {r["chunk_id"] for r in found}
            refs = case["source_refs"]
            coverage = all(source_ids[ref] in ids for ref in refs) if refs else None
            row = {"id": case["id"], "group": case["group"], "query": case["question"], "failure": None,
                "required_source_coverage": coverage, "latency_ms": round((time.monotonic()-start)*1000, 1),
                "sources": [{"chunk_id": r["chunk_id"], "locator": r["section_path"], "content_sha256": hashlib.sha256(r["content_text"].encode()).hexdigest()} for r in found]}
        except Exception as exc:
            row = {"id": case["id"], "group": case["group"], "failure": type(exc).__name__, "required_source_coverage": False if case["source_refs"] else None, "latency_ms": round((time.monotonic()-start)*1000, 1)}
        rows.append(row)
        print(json.dumps({k: row.get(k) for k in ("id", "required_source_coverage", "failure", "latency_ms")}), flush=True)
    measured = [r for r in rows if "skipped" not in r]
    source_cases = [r for r in measured if r["required_source_coverage"] is not None]
    timings = [r["latency_ms"] for r in measured]
    return {"mode": "real_retrieval", "configuration": "current public BM25+BGE-M3/RRF/reranker/parent store, existing pinned index",
        "index_fingerprint": store.fingerprint, "native_before": before, "native_after": native_snapshot(),
        "paid_before": paid_before, "paid_after": paid_snapshot(), "provider_calls": 0,
        "source_covered": sum(r["required_source_coverage"] for r in source_cases), "source_cases_measured": len(source_cases),
        "latency_p50_ms": percentile(timings, .5), "latency_p95_ms": percentile(timings, .95), "results": rows,
        "limits": "Raw standalone query retrieval; history is recorded in dataset but NOT rewritten here. Missing-evidence cases have no gold recall score. Returned-source presence is not correctness, citation entailment or final held-out quality. Failures remain in denominators."}


def frames(text):
    events = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        pairs = dict(line.split(":", 1) for line in block.splitlines() if ":" in line)
        if "data" in pairs:
            events.append((pairs.get("event", "").strip(), json.loads(pairs["data"])))
    return events


def generation(dataset, only, max_calls):
    import httpx
    before = paid_snapshot()
    if before["hard_cap_usd"] != "3" or before["call_cap"] != 8500:
        raise RuntimeError("retained authorized budget does not match; do not reset/raise it")
    results = []
    selected = [c for c in dataset["cases"] if c["id"] in only.split(",")]
    with httpx.Client(base_url="http://127.0.0.1:8002", trust_env=False, timeout=45) as client:
        auth = client.post("/v1/auth/demo-login", json={"account": "SV001"}); auth.raise_for_status()
        headers = {"Authorization": "Bearer " + auth.json()["token"]}
        for case in selected:
            current = paid_snapshot()
            turns = len(case["history"])+1
            # Include sensitive_classifier and route_intent as well as bounded
            # generation/regeneration and semantic verification (up to six).
            if current["calls"]-before["calls"]+6*turns > max_calls or current["call_cap"]-current["calls"] < 6*turns:
                results.append({"id": case["id"], "skipped": "provider call headroom insufficient"}); continue
            created = client.post("/v1/conversations", headers=headers, json={})
            if created.status_code != 201:
                results.append({"id": case["id"], "failure": "conversation_http_" + str(created.status_code)}); continue
            cid = created.json()["id"]
            row = {"id": case["id"], "conversation_id": cid, "turns": [], "expected_behavior": case["expected_behavior"],
                   "required_concepts": case["required_concepts"], "manual_rubric": None}
            for turn in [*case["history"], {"content": case["question"]}]:
                usage = native_snapshot()
                if usage["caps"]["inference"]-usage["counts"]["inference"] < 9:
                    row["turns"].append({"question": turn["content"], "skipped": "native inference headroom insufficient"})
                    break
                start = time.monotonic()
                snapshot = paid_snapshot()
                response = client.post(f"/v1/conversations/{cid}/messages:stream", headers=headers, json={"content": turn["content"]})
                events = frames(response.text) if response.status_code == 200 else []
                final = next((v for kind, v in reversed(events) if kind == "message.completed"), None)
                failure = next((v.get("code") for kind, v in events if kind == "message.failed"), None)
                if response.status_code != 200:
                    failure = "stream_http_" + str(response.status_code)
                sources = []
                if final:
                    for mapping in final["citations"]:
                        c = mapping["citation"]
                        source = client.get(f"/v1/conversations/{cid}/messages/{final['message_id']}/citations/{c['citation_id']}/source", headers=headers)
                        if source.status_code == 200:
                            value = source.json()
                            sources.append({"citation": c, "source": value,
                                "hash_matches": hashlib.sha256(value["content_text"].encode()).hexdigest() == value["content_sha256"]})
                        else:
                            sources.append({"citation": c, "http_status": source.status_code, "hash_matches": False})
                history = client.get(f"/v1/conversations/{cid}/messages?limit=100", headers=headers)
                after = paid_snapshot()
                row["turns"].append({"question": turn["content"], "latency_ms": round((time.monotonic()-start)*1000), "final": final,
                    "failure": failure, "sources": sources, "history_http_status": history.status_code,
                    "provider_calls": after["calls"]-snapshot["calls"],
                    "input_tokens_charged": after["input_tokens_charged"]-snapshot["input_tokens_charged"],
                    "output_tokens_charged": after["output_tokens_charged"]-snapshot["output_tokens_charged"],
                    "conservative_cost_usd": str(float(after["conservative_charged_usd"])-float(snapshot["conservative_charged_usd"])),
                    "history": history.json() if history.status_code == 200 else None})
                print(json.dumps({"id": case["id"], "class": (final or {}).get("response_class"), "failure": failure,
                    "answer": (final or {}).get("content", ""), "provider_calls": after["calls"]-snapshot["calls"]}, ensure_ascii=False), flush=True)
                time.sleep(7)
            results.append(row)
    after = paid_snapshot()
    return {"mode": "live_generation_existing_public_writer_via_certificate_proxy", "paid_before": before, "paid_after": after,
            "runner_call_estimate_exceeded": after["calls"]-before["calls"] > max_calls,
            "max_additional_provider_calls": max_calls, "results": results,
            "limits": "Small development sample; costs are conservative reservations, not invoice. Manual source/claim review is required. Failed turns never count as correct answers."}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["retrieval", "generation"])
    parser.add_argument("--output", type=lambda p: checked(__import__("pathlib").Path(p), STATE), required=True)
    parser.add_argument("--only", default="CERT-DEV-001,CERT-DEV-008,CERT-DEV-021,CERT-DEV-031,CERT-DEV-045")
    parser.add_argument("--max-provider-calls", type=int, default=18, choices=range(1, 19))
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("retain existing report; choose new output")
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    report = asyncio.run(retrieval(data)) if args.mode == "retrieval" else generation(data, args.only, args.max_provider_calls)
    report["dataset_sha256"] = hashlib.sha256(DATASET.read_bytes()).hexdigest()
    retain(args.output, report)
