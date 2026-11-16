"""Probe retained real retrieval inputs without a database or paid generation.

This is native inference diagnostics only, never answer/release acceptance.
Each input runs once; all failures and shared accounting remain retained.
"""
import asyncio
from datetime import UTC, datetime
import hashlib
import json
from time import perf_counter

import httpx

from knowledge_platform import ROOT, STATE, checked_path, model_budget, retain
from campus247.application.knowledge.platform_models import EMBED_MODEL, EMBED_REVISION, RERANK_MODEL, RERANK_REVISION


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--conditional-query", action="store_true", help="Only recheck changed conditional retrieval queries; full user intent is retained downstream")
    mode.add_argument("--concurrency-probe", action="store_true", help="Two concurrent query embeddings only; no answer or application-load acceptance")
    args = parser.parse_args()
    source = checked_path(ROOT / "infra/local/knowledge-automation-20261026/retrieval-diagnostic-20261027T023239296147/receipt.json", ROOT)
    raw = source.read_bytes()
    prior = json.loads(raw)
    namespace = checked_path(ROOT / json.loads((STATE / "model-accounting.json").read_text(encoding="utf-8"))["native_namespace"], ROOT)
    scope = checked_path(ROOT / "infra/local/knowledge-automation-20261026" /
        ("native-probe-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")), ROOT)
    report = {"started_at": datetime.now(UTC), "scope": "retained real inputs; native diagnostics only",
        "source_receipt": str(source.relative_to(ROOT)), "source_receipt_sha256": hashlib.sha256(raw).hexdigest(),
        "paid_generation_calls": 0, "conditional_query_projection": args.conditional_query, "concurrency_probe": args.concurrency_probe,
        "native_before": model_budget(), "calls": [], "namespace": str(namespace.relative_to(ROOT))}
    try:
        async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=15) as client:
            for port, model, revision in ((18081, EMBED_MODEL, EMBED_REVISION), (18082, RERANK_MODEL, RERANK_REVISION)):
                response = await client.get(f"http://127.0.0.1:{port}/info")
                response.raise_for_status()
                info = response.json()
                if (info.get("model_id"), info.get("model_sha")) != (model, revision):
                    raise ValueError("Exact retained native model identity required")
            if args.concurrency_probe:
                from campus247_worker.knowledge import available_memory
                report["available_memory_before"] = available_memory()
                if report["available_memory_before"] is None or report["available_memory_before"] < 2*1024**3:
                    raise RuntimeError("Resource floor cannot be verified; no inference dispatched")
                async def concurrent_embed(case):
                    started = perf_counter()
                    item = {"case": case["name"], "endpoint": "/embed", "concurrent_requests": 2,
                        "input_sha256": hashlib.sha256(case["question"].encode()).hexdigest()}
                    report["calls"].append(item)
                    try:
                        response = await client.post("http://127.0.0.1:18081/embed",
                            json={"inputs": [case["question"]], "normalize": True, "truncate": False})
                        item["status"] = response.status_code
                        item["response_sha256"] = hashlib.sha256(response.content).hexdigest()
                    except httpx.HTTPError as error:
                        item["error_type"] = type(error).__name__
                    item["elapsed_seconds"] = perf_counter()-started
                await asyncio.gather(*(concurrent_embed(case) for case in prior["cases"]))
                report["available_memory_after"] = available_memory()
            for case in (() if args.concurrency_probe else prior["cases"]):
                from campus247.application.retrieval.conditional_query import conditional_retrieval_question
                query = conditional_retrieval_question(case["question"]) if args.conditional_query else case["question"]
                if args.conditional_query and query == case["question"]:
                    continue
                requests = [(18081, "/embed", {"inputs": [query], "normalize": True, "truncate": False})]
                candidates = case.get("rerank_inputs", [])
                if candidates:
                    requests.append((18082, "/rerank", {"query": query if args.conditional_query else case.get("rerank_query", query),
                        "texts": [row["text"] for row in candidates], "raw_scores": True, "return_text": False, "truncate": False}))
                for port, endpoint, payload in requests:
                    before = model_budget()
                    started = perf_counter()
                    item = {"case": case["name"], "endpoint": endpoint,
                        "retrieval_query": query, "full_question": case["question"],
                        "input_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
                        "candidate_ids": [row["id"] for row in candidates] if endpoint == "/rerank" else [],
                        "input_characters": [len(text) for text in payload.get("texts", payload.get("inputs", []))]}
                    report["calls"].append(item)
                    try:
                        response = await client.post(f"http://127.0.0.1:{port}{endpoint}", json=payload)
                        item["status"] = response.status_code
                        value = response.json()
                        item["response_sha256"] = hashlib.sha256(response.content).hexdigest()
                        if endpoint == "/rerank" or response.status_code != 200:
                            item["result"] = value
                        else:
                            import math
                            item["vector_shape"] = [len(value), len(value[0])]
                            item["l2_norm"] = math.sqrt(sum(v*v for v in value[0]))
                    except (httpx.HTTPError, ValueError, TypeError, IndexError) as error:
                        item["error_type"] = type(error).__name__
                    item["elapsed_seconds"] = perf_counter() - started
                    item["native_before"], item["native_after"] = before, model_budget()
                    print(json.dumps({k: item[k] for k in ("case", "endpoint", "elapsed_seconds", "status") if k in item}), flush=True)
    finally:
        report.update(finished_at=datetime.now(UTC), native_after=model_budget())
        first = report["native_before"]["usage_counts"]["inference"]
        last = report["native_after"]["usage_counts"]["inference"]
        report["native_receipts"] = []
        for ordinal in range(first+1, last+1):
            for suffix in ("reservation", "result"):
                path = checked_path(namespace / f"native-{ordinal:05d}-{suffix}.json", ROOT)
                if path.is_file():
                    report["native_receipts"].append({"file": path.name, "value": json.loads(path.read_bytes())})
        retain(scope / "receipt.json", report)
        print(json.dumps({"receipt": str(scope / "receipt.json")}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
