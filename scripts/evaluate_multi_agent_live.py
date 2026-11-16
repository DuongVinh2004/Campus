"""Fresh integrated HTTP evaluation; one exclusive artifact per development case.

No Gateway is opened here. Only user questions enter the application. Rubric,
gold concepts and expected behavior stay in the report, outside model context.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx

from multi_agent_workspace import ROOT, STATE, checked, retain
from evaluate_certificate_rag import frames
from multi_agent_live_resources import paid_view as paid_snapshot, native_view as native_snapshot

DATASET = ROOT / "evals/datasets/certificate-development-20261013.json"


class PacedClient:
    """Stay below the existing 30 conversation requests/minute abuse control."""
    def __init__(self, client, interval=2.2):
        self.client, self.interval, self.last = client, interval, 0.0

    def pace(self):
        time.sleep(max(0, self.last+self.interval-time.monotonic()))
        self.last = time.monotonic()

    def request(self, method, path, **kwargs):
        self.pace()
        return self.client.request(method, path, **kwargs)

    def stream(self, method, path, **kwargs):
        self.pace()
        return self.client.stream(method, path, **kwargs)


def usage_delta(before, after, native_before, native_after):
    return {"provider_calls": after["calls"]-before["calls"],
        "input_tokens_charged": after["input_tokens_charged"]-before["input_tokens_charged"],
        "output_tokens_charged": after["output_tokens_charged"]-before["output_tokens_charged"],
        "conservative_cost_usd": str(Decimal(after["conservative_charged_usd"])-Decimal(before["conservative_charged_usd"])),
        "actual_billed_usd": None,
        "native": {key: native_after["counts"][key]-native_before["counts"][key]
                   for key in ("http", "inference", "tokens")}}


def checkpoint_trace(run_id, conversation_id):
    """Read only allowlisted application evidence; never model inputs/secrets."""
    path = checked(STATE / "agent-runs.sqlite3", STATE)
    with sqlite3.connect(path.as_uri()+"?mode=ro", uri=True) as conn:
        row = conn.execute("SELECT record FROM agent_run WHERE id=? AND conversation=?",
                           (run_id, conversation_id)).fetchone()
    if row is None:
        return None
    record = json.loads(row[0])
    controller = record.get("controller", {})
    return {"controller": {key: controller[key] for key in
        ("items", "coverage", "evidence_refs", "queries", "no_progress") if key in controller},
        **{key: record[key] for key in ("claims", "claim_attempts", "verification_requests", "task_proposals", "coverage_proposals",
            "pending", "duration_ms", "config_fingerprint", "snapshot", "error_codes",
            "semantic_question_coverage") if key in record}}


def run_turn(client, headers, conversation_id, question):
    before, native_before = paid_snapshot(), native_snapshot()
    started = time.monotonic()
    row = {"question": question, "failure": None, "final": None, "sources": [], "manual_rubric": None}
    try:
        parts = []
        size = 0
        with client.stream("POST", f"/v1/conversations/{conversation_id}/messages:stream",
                           headers=headers, json={"content": question}) as response:
            dispatched = client.last
            row["runner_pacing_ms"] = round((dispatched-started)*1000)
            for part in response.iter_text():
                size += len(part.encode())
                if size > 1_048_576:
                    raise ValueError("stream response bound")
                parts.append(part)
                text = "".join(parts)
                elapsed = round((time.monotonic()-dispatched)*1000)
                if "event: agent.status" in text:
                    row.setdefault("first_progress_ms", elapsed)
                if "event: message.completed" in text:
                    row.setdefault("completion_frame_ms", elapsed)
            row["latency_ms"] = round((time.monotonic()-dispatched)*1000)
        row["stream_http_status"] = response.status_code
        if response.status_code != 200:
            row["failure"] = "stream_http_"+str(response.status_code)
        else:
            events = frames("".join(parts))
            row["progress"] = [data for kind, data in events if kind == "agent.status"]
            row["final"] = next((data for kind, data in reversed(events) if kind == "message.completed"), None)
            row["failure"] = next((data.get("code", "stream_failed") for kind, data in events if kind == "message.failed"), None)
            if row["final"] is None and row["failure"] is None:
                row["failure"] = "terminal_missing"
            final = row["final"]
            if final:
                if final["response_class"] == "system_error":
                    row["failure"] = "system_error"
                for mapping in final["citations"]:
                    citation = mapping["citation"]
                    source = client.request("GET", f"/v1/conversations/{conversation_id}/messages/{final['message_id']}/citations/{citation['citation_id']}/source", headers=headers)
                    value = source.json() if source.status_code == 200 else None
                    row["sources"].append({"citation": citation, "http_status": source.status_code,
                        "source": value, "hash_matches": bool(value and hashlib.sha256(
                            value["content_text"].encode()).hexdigest() == value["content_sha256"])})
                run_id = final.get("run_id")
                if run_id:
                    path = f"/v1/conversations/{conversation_id}/agent-runs/{run_id}"
                    run = client.request("GET", path, headers=headers)
                    row["run_http_status"] = run.status_code
                    row["run"] = run.json() if run.status_code == 200 else None
                    event_response = client.request("GET", path+"/events", headers=headers)
                    row["events"] = event_response.json() if event_response.status_code == 200 else None
                    row["checkpoint"] = checkpoint_trace(run_id, conversation_id)
            history = client.request("GET", f"/v1/conversations/{conversation_id}/messages?limit=100", headers=headers)
            row["history_http_status"] = history.status_code
            row["history"] = history.json() if history.status_code == 200 else None
            row["history_readback_equal"] = bool(row["final"] and row["history"] and
                row["history"]["items"][-1].get("final_result") == row["final"])
    except (httpx.HTTPError, ValueError, KeyError, sqlite3.Error) as failure:
        # Request outcome may be unknown; never automatically resend it.
        row["failure"] = type(failure).__name__
        row.setdefault("latency_ms", round((time.monotonic()-started)*1000))
    after, native_after = paid_snapshot(), native_snapshot()
    row.update(usage_delta(before, after, native_before, native_after))
    row["readback_elapsed_ms"] = round((time.monotonic()-started)*1000)-row["latency_ms"]
    return row


def selected_cases(dataset, only):
    if not only:
        return dataset["cases"]
    names = only.split(",")
    known = {case["id"] for case in dataset["cases"]}
    if len(set(names)) != len(names) or not set(names) <= known:
        raise ValueError("unique existing case IDs required")
    return [case for case in dataset["cases"] if case["id"] in names]


def summary(results):
    turns = [turn for case in results for turn in case.get("turns", [])]
    latencies = sorted(turn["latency_ms"] for turn in turns)
    return {"cases_recorded": len(results), "turns_recorded": len(turns),
        "failed_turns": sum(bool(turn["failure"]) for turn in turns),
        "history_readback_equal": sum(turn.get("history_readback_equal", False) for turn in turns),
        "citations_opened": sum(source["hash_matches"] for turn in turns for source in turn["sources"]),
        "citation_readback_failures": sum(not source["hash_matches"] for turn in turns for source in turn["sources"]),
        "latency_p50_ms": latencies[max(0, math.ceil(len(latencies)*.5)-1)] if latencies else None,
        "latency_p95_ms": latencies[max(0, math.ceil(len(latencies)*.95)-1)] if latencies else None,
        "correctness": None, "completeness": None, "citation_entailment": None,
        "quality_verdict": "not_verified_pending_source_based_review"}


def should_halt(results):
    """Three consecutive operational failures halt paid dispatch, preserving rows."""
    return len(results) >= 3 and all(
        row.get("failure") or any(turn.get("failure") for turn in row.get("turns", []))
        for row in results[-3:])


def main(output, only=None):
    output = checked(output, STATE)
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = selected_cases(dataset, only)
    destinations = [checked(output.with_name(output.stem+"-"+case["id"]+".json"), STATE) for case in cases]
    if output.exists() or any(path.exists() for path in destinations):
        raise FileExistsError("retain earlier results; choose a new output stem")
    before, native_before = paid_snapshot(), native_snapshot()
    started = datetime.now(timezone.utc).isoformat()
    results = []
    with httpx.Client(base_url="http://127.0.0.1:8003", trust_env=False, timeout=45,
                      follow_redirects=False) as http:
        client = PacedClient(http)
        health = client.request("GET", "/health/live"); health.raise_for_status()
        if health.json().get("mode") != "multi_agent_integrated" or health.json().get("owns_paid_ledger") is not True:
            raise RuntimeError("fresh live integrated writer required; guarded/proxy runtime is not generation")
        login = client.request("POST", "/v1/auth/demo-login", json={"account": "SV001"}); login.raise_for_status()
        headers = {"Authorization": "Bearer "+login.json()["token"]}
        for case, destination in zip(cases, destinations, strict=True):
            created = client.request("POST", "/v1/conversations", headers=headers, json={})
            row = {"id": case["id"], "question": case["question"], "history": case["history"],
                "expected_behavior": case["expected_behavior"], "source_refs": case["source_refs"],
                "required_concepts": case["required_concepts"], "manual_rubric": None, "turns": []}
            if created.status_code != 201:
                row["failure"] = "conversation_http_"+str(created.status_code)
            else:
                row["conversation_id"] = created.json()["id"]
                for turn in [*case["history"], {"role": "user", "content": case["question"]}]:
                    if turn["role"] != "user":
                        raise ValueError("only user history may enter the live application")
                    result = run_turn(client, headers, row["conversation_id"], turn["content"])
                    row["turns"].append(result)
                    print(json.dumps({"case": case["id"], "response_class": (result["final"] or {}).get("response_class"),
                        "failure": result["failure"], "calls": result["provider_calls"], "latency_ms": result["latency_ms"]}), flush=True)
                    if result["failure"]:
                        break
            retain(destination, row)
            results.append(row)
            if should_halt(results):
                break
    after, native_after = paid_snapshot(), native_snapshot()
    report = {"mode": "fresh_live_integrated_multi_agent_http", "split": "development",
        "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
        "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(), "health": health.json(),
        "paid_before": before, "paid_after": after, "native_before": native_before, "native_after": native_after,
        "usage": usage_delta(before, after, native_before, native_after), "summary": summary(results),
        "aborted": len(results) != len(cases), "expected_cases": len(cases),
        "abort_reason": "consecutive_operational_failures" if len(results) != len(cases) else None,
        "not_verified_case_ids": [case["id"] for case in cases[len(results):]],
        "results": results, "limitations": "No architecture comparison. Failure is not correctness. Cost is a conservative ledger charge, not invoice. Manual claim/source review remains required. No request retry or action confirmation is sent."}
    retain(output, report)
    print(json.dumps(report["summary"]), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only")
    args = parser.parse_args()
    main(args.output, args.only)
