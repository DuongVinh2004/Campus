"""Live model/neural tools with one explicitly controlled initial result gap.

Run only while the public API writer is stopped. This in-process ASGI probe
holds the same exclusive Gateway lease; it is a fault check, not Dev48 quality
or a TCP/SSE timing measurement. Sources, gates and ceilings are unchanged.
"""
import argparse
import asyncio
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from multi_agent_workspace import STATE, checked, retain
from multi_agent_live_resources import paid_view, native_view
from launch_multi_agent import listening
from evaluate_multi_agent_live import checkpoint_trace, usage_delta
from evaluate_certificate_rag import frames
from run_multi_agent import make_app

QUESTION = "Theo quy trình trong sổ tay HUCE, chuyên viên lấy dấu giấy xác nhận sinh viên tại phòng nào?"


async def probe(output):
    output = checked(output, STATE)
    if output.exists() or listening(8003):
        raise RuntimeError("new output and stopped public API writer required")
    before, native_before = paid_view(), native_view()
    started = time.monotonic()
    app = make_app(mode="live")
    workflow = app.state.integrated_rag_app.state.multi_agent_workflow
    workflow.snapshot = {**workflow.snapshot, "controlled_fault": "one_initial_result_omission"}
    original_search = workflow._context_search_fn
    searches, sources = [], []
    failure, final, history, run, events, checkpoint = None, None, None, None, None, None

    async def initial_gap(query, context):
        rows = await original_search(query, context)  # Actual guarded neural search.
        omitted = len(searches) == 0
        searches.append({"query_sha256": hashlib.sha256(query.encode()).hexdigest(),
            "actual_candidate_ids": [row["chunk_id"] for row in rows],
            "actual_candidates": len(rows), "returned_candidates": 0 if omitted else len(rows),
            "controlled_result_omission": omitted})
        return [] if omitted else rows

    workflow._context_search_fn = initial_gap
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                base_url="http://127.0.0.1:8003", trust_env=False, timeout=45) as client:
            login = await client.post("/v1/auth/demo-login", json={"account": "SV001"})
            login.raise_for_status()
            headers = {"Authorization": "Bearer "+login.json()["token"]}
            created = await client.post("/v1/conversations", headers=headers, json={})
            created.raise_for_status()
            cid = created.json()["id"]
            response = await client.post(f"/v1/conversations/{cid}/messages:stream", headers=headers,
                                         json={"content": QUESTION})
            response.raise_for_status()
            parsed = frames(response.text)
            final = next((data for kind, data in reversed(parsed) if kind == "message.completed"), None)
            failure = next((data.get("code", "stream_failed") for kind, data in parsed if kind == "message.failed"), None)
            if final:
                path = f"/v1/conversations/{cid}/agent-runs/{final['run_id']}"
                result = await client.get(path, headers=headers); result.raise_for_status(); run = result.json()
                result = await client.get(path+"/events", headers=headers); result.raise_for_status(); events = result.json()
                checkpoint = checkpoint_trace(final["run_id"], cid)
                for mapping in final["citations"]:
                    ref = mapping["citation"]
                    path = f"/v1/conversations/{cid}/messages/{final['message_id']}/citations/{ref['citation_id']}/source"
                    result = await client.get(path, headers=headers); result.raise_for_status()
                    source = result.json()
                    sources.append({"citation": ref, "source": source,
                        "hash_matches": hashlib.sha256(source["content_text"].encode()).hexdigest() == source["content_sha256"]})
                result = await client.get(f"/v1/conversations/{cid}/messages?limit=100", headers=headers)
                result.raise_for_status(); history = result.json()
    except Exception as error:
        failure = type(error).__name__  # Never persist token, raw request or error repr.
    finally:
        workflow._gateway.close()
    after, native_after = paid_view(), native_view()
    rows = (events or {}).get("events", [])
    statuses = [row["status"] for row in rows if row["tool"] == "search_knowledge"]
    passed = bool(not failure and final and final["response_class"] == "grounded_answer"
        and len(searches) >= 2 and searches[0]["actual_candidates"] > 0
        and statuses[:2] == ["empty", "completed"] and sources and all(row["hash_matches"] for row in sources)
        and (history or {}).get("items", [{}])[-1].get("final_result") == final
        and run and all(row["status"] == "supported" for row in run["coverage"]))
    report = {"mode": "live_model_real_neural_tools_controlled_initial_result_gap", "passed": passed,
        "transport": "in_process_ASGI", "normal_application_quality_run": False,
        "fault": "First real search executes and charges native usage, then its candidates are omitted once; subsequent searches are unchanged.",
        "question": QUESTION, "created_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": round((time.monotonic()-started)*1000), "failure": failure,
        "searches": searches, "search_event_statuses": statuses, "final": final,
        "run": run, "events": events, "checkpoint": checkpoint, "sources": sources,
        "history": history, "paid_before": before, "paid_after": after,
        "native_before": native_before, "native_after": native_after,
        "usage": usage_delta(before, after, native_before, native_after),
        "limitations": "Only the initial result gap is injected. Model decisions, original source readbacks, neural tools and budget charges are live. No TCP/SSE latency or general usability claim. No confirmation/action request, source/gold/threshold edit or automatic retry."}
    retain(output, report)
    print(json.dumps({"passed": passed, "failure": failure, "search_event_statuses": statuses,
                      "provider_calls": report["usage"]["provider_calls"]}), flush=True)
    return passed


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if asyncio.run(probe(args.output)) else 1)
