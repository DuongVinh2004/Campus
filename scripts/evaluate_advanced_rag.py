"""Real-source before/after retrieval and bounded HTTP/SSE generation evaluation."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from run_advanced_rag import CAMPUS, CORPUS, ROOT, TENANT, index_path, store
from run_public_rag import checked

DATASET = ROOT / "evals/datasets/advanced-public-rag-20261013.json"


def cases():
    return json.loads(DATASET.read_text(encoding="utf-8"))["cases"]


def context():
    from campus247.domain.retrieval import (
        AuthorizedScope,
        RetrievalContext,
        SimulationPolicy,
    )
    return RetrievalContext(AuthorizedScope(TENANT, CAMPUS, "eval-actor", frozenset({"STUDENT"}),
        frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})),
        "vi", datetime.now(UTC), SimulationPolicy.DENY, "1" * 32)


def retain(path, value):
    with checked(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


async def retrieval(target, only=None):
    from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore
    advanced = store()
    advanced.load_vectors(json.loads(index_path(advanced).read_text(encoding="utf-8")))
    baseline = PublicKnowledgeStore(CORPUS, tenant_id=TENANT, campus_id=CAMPUS,
                                   faq_directory=ROOT / "data/huce-faq-20261013")
    rows = []
    selected = [case for case in cases() if not only or case["id"] in only.split(",")]
    if not selected:
        raise ValueError("unknown retrieval cases")
    for case in selected:
        expected = {advanced.rows[i]["chunk_id"] for i in case["parents"]}
        start = time.monotonic()
        old = await baseline.search(case["question"], context())
        old_ms = (time.monotonic() - start) * 1000
        start = time.monotonic()
        try:
            new = await advanced.search(case["question"], context())
            failure = None
        except Exception as error:  # noqa: BLE001 -- retain safe phase failure without input/exception text
            new, failure = [], type(error).__name__
        row = {"id": case["id"], "question": case["question"],
            "baseline_hit": bool(expected & {r["chunk_id"] for r in old}),
            "advanced_hit": bool(expected & {r["chunk_id"] for r in new}),
            "baseline_ms": round(old_ms), "advanced_ms": round((time.monotonic() - start) * 1000),
            "expected_sources": [{"chunk_id": r["chunk_id"], "hash": r["quote_span_hash"], "section": r["section_path"]}
                for i,r in enumerate(advanced.rows) if i in case["parents"]],
            "selected_sources": [{"chunk_id": r["chunk_id"], "section": r["section_path"], "score": r["score"]} for r in new],
            "failure": failure}
        rows.append(row)
        print(json.dumps({k: row[k] for k in ("id", "baseline_hit", "advanced_hit", "advanced_ms", "failure")}), flush=True)
    retain(target, {"dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(), "index": advanced.fingerprint,
        "scope": "real_public_sources_real_BGE_models", "baseline_coverage": sum(r["baseline_hit"] for r in rows) / len(rows),
        "advanced_coverage": sum(r["advanced_hit"] for r in rows) / len(rows), "results": rows,
        "metric": "question coverage in returned parent context; not Recall@10 or answer correctness"})


def frames(value):
    events = []
    for block in value.replace("\r\n", "\n").split("\n\n"):
        parts = dict(line.split(":", 1) for line in block.splitlines() if ":" in line)
        if "data" in parts:
            events.append((parts.get("event", "").strip(), json.loads(parts["data"])))
    return events


def chat(target, limit, only=None):
    import httpx
    results = []
    with httpx.Client(base_url="http://127.0.0.1:8001", trust_env=False, timeout=45) as client:
        auth = client.get("/v1/auth/demo-session")
        auth.raise_for_status()
        headers = {"Authorization": "Bearer " + auth.json()["token"]}
        selected = cases()[:limit]
        if only:
            selected = [case for case in cases() if case["id"] in only.split(",")]
        selected += [{"id": "capabilities", "question": "Bạn giúp được gì?", "answer_terms": ["tra cứu"]}]
        for case in selected:
            created = client.post("/v1/conversations", headers=headers, json={})
            created.raise_for_status()
            cid = created.json()["id"]
            start = time.monotonic()
            response = client.post(f"/v1/conversations/{cid}/messages:stream", headers=headers, json={"content": case["question"]})
            events = frames(response.text)
            final = next((v for kind,v in reversed(events) if kind == "message.completed"), None)
            failure = next((v.get("code") for kind,v in events if kind == "message.failed"), None)
            opened = []
            if final:
                for mapping in final["citations"]:
                    citation = mapping["citation"]
                    source = client.get(f"/v1/conversations/{cid}/messages/{final['message_id']}/citations/{citation['citation_id']}/source", headers=headers)
                    if source.status_code == 200:
                        value = source.json()
                        opened.append(hashlib.sha256(value["content_text"].encode()).hexdigest() == value["content_sha256"])
                    else:
                        opened.append(False)
            answer = (final or {}).get("content", "").casefold().replace("2,0", "2.0")
            expected_class = "clarification_request" if case["id"] == "capabilities" else "grounded_answer"
            passed = bool(final and final["response_class"] == expected_class
                          and all(term.casefold() in answer for term in case["answer_terms"])
                          and (expected_class != "grounded_answer" or opened and all(opened)))
            row = {"id": case["id"], "question": case["question"], "passed": passed, "failure": failure,
                   "latency_ms": round((time.monotonic() - start) * 1000), "final": final, "citation_hash_checks": opened}
            results.append(row)
            print(json.dumps({"id": row["id"], "passed": passed, "failure": failure,
                "latency_ms": row["latency_ms"], "response_class": final["response_class"] if final else None,
                "answer": (final or {}).get("content", "")[:200]}, ensure_ascii=False), flush=True)
            time.sleep(7)  # Preserve the application's request-rate limit.
    retain(target, {"scope": "live_provider_actual_HTTP_SSE_and_source_readback", "results": results,
                   "passed": sum(row["passed"] for row in results), "total": len(results),
                   "correctness_limit": "Answer term checks and source hashes; claims need source-based review, not a correctness certificate."})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("retrieval", "chat"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--only")
    args = parser.parse_args()
    target = checked(args.output)
    if target.exists():
        raise ValueError("new evidence file required")
    if args.mode == "retrieval":
        asyncio.run(retrieval(target, args.only))
    else:
        chat(target, args.limit, args.only)
