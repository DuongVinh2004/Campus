"""Prepared development runner: same existing HTTP writer; no Gateway is opened here."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

from build_policy_graph import ROOT, destination
from multi_agent_live_resources import paid_view, native_view, STAGE5_PAID_CAPS

DATASET = ROOT / "evals/datasets/policy-graph-development-20261014.json"


def preflight():
    from campus247.application.multi_agent.contracts import MultiAgentPolicy
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    paid, native = paid_view(), native_view()
    policy = MultiAgentPolicy()
    runs = data["max_live_query_runs"] + data["max_live_extraction_runs"] + data["reserved_repair_runs"]
    calls = runs * policy.max_model_calls
    conservative_reservation = Decimal(runs*policy.max_reserved_tokens)*Decimal("1.2")/Decimal(1000000)
    native_sequences = data["max_live_query_runs"] * policy.max_searches * 9
    admitted = (paid["call_cap"]-paid["calls"] >= calls and Decimal(paid["remaining_usd"]) >= conservative_reservation
        and native["caps"]["inference"]-native["counts"]["inference"] >= native_sequences
        and native["caps"]["tokens"]-native["counts"]["tokens"] >= native_sequences*900
        and native["caps"]["http"]-native["counts"]["http"] >= data["max_live_query_runs"]*policy.max_searches*18)
    return {"admitted": admitted, "run_envelopes": runs, "reserved_provider_calls": calls,
        "remaining_calls": paid["call_cap"]-paid["calls"], "proposed_call_cap": max(paid["call_cap"], STAGE5_PAID_CAPS["calls"]),
        "total_usd_cap_unchanged": paid["hard_cap_usd"], "conservative_new_reservation_usd": str(conservative_reservation),
        "paid_snapshot": paid, "native_snapshot": native, "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        "new_writer_opened": False, "live_calls_dispatched": 0}


def retain(name, value):
    with destination(name).open("x", encoding="utf-8") as out:
        json.dump(value, out, ensure_ascii=False, indent=2)


def execute(receipt_path):
    check = preflight()
    if not check["admitted"]:
        raise RuntimeError("insufficient authorized full campaign headroom; zero live dispatch")
    path = receipt_path.resolve(strict=True)
    if not path.is_relative_to(ROOT):
        raise ValueError("workspace runtime receipt required")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    command = receipt.get("commands", {}).get("api", [])
    if ("--policy-graph" not in command or "huce-policy-development-v1" not in command
            or receipt.get("paid_writer") != "api8003_only" or not receipt.get("api_only")):
        raise ValueError("stage5 exclusive-writer API-only receipt required")
    import httpx
    from evaluate_multi_agent_live import PacedClient, run_turn
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    retain("live-campaign-admission-01.json", {**check, "receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    with httpx.Client(base_url="http://127.0.0.1:8003", timeout=40, trust_env=False) as transport:
        client = PacedClient(transport)
        health = client.request("GET", "/health/live"); health.raise_for_status()
        if not health.json().get("owns_paid_ledger"):
            raise ValueError("existing live writer required")
        login = client.request("POST", "/v1/auth/demo-login", json={"account": "SV001"}); login.raise_for_status()
        headers = {"Authorization": "Bearer "+login.json()["token"]}
        graph = client.request("POST", "/v1/policy-graph/relations:search", headers=headers,
            json={"query": "quy trình xác nhận"}); graph.raise_for_status()
        if graph.json().get("graph_id") != data["graph_id"]:
            raise ValueError("active reviewed graph version mismatch")
        for i, question in enumerate(data["questions"], 1):
            name = f"live-case-{i:03d}-01.json"
            if destination(name).exists() or destination(f"live-attempt-{i:03d}-01.json").exists():
                raise FileExistsError("retain prior attempts; never replay as fresh")
            retain(f"live-attempt-{i:03d}-01.json", {"question": question, "status": "attempt_reserved_no_automatic_retry"})
            created = client.request("POST", "/v1/conversations", headers=headers, json={"title": f"Policy graph S5-{i:03d}"}); created.raise_for_status()
            cid = created.json()["id"]
            result = run_turn(client, headers, cid, question)
            graph_events = [e for e in (result.get("events") or {}).get("events", []) if e["tool"] == "search_policy_relations"]
            retain(name, {"case_id": f"S5-LIVE-{i:03d}", "conversation_id": cid, "question": question,
                "turn": result, "graph_events": graph_events, "quality_review": "not_verified_requires_source_review"})
            if result.get("failure"):
                break  # No blind resend after uncertain/provider failures.
        admin = client.request("POST", "/v1/auth/demo-login", json={"account": "KA001"}); admin.raise_for_status()
        admin_headers = {"Authorization": "Bearer "+admin.json()["token"]}
        for i, targets in enumerate(data["extraction_targets"], 1):
            retain(f"live-extraction-attempt-{i:02d}-01.json", {"targets": targets, "status": "attempt_reserved"})
            response = client.request("POST", f"/v1/policy-graph/versions/{data['graph_id']}:extract-candidate",
                headers=admin_headers, json={"target_ids": targets})
            retain(f"live-extraction-{i:02d}-01.json", {"http_status": response.status_code,
                "result": response.json(), "quality_review": "not_verified_candidate_only"})
            if response.status_code != 200:
                break


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--runtime-receipt", type=Path)
    parser.add_argument("--preflight-output", default=None)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if args.execute:
        if args.runtime_receipt is None:
            parser.error("--runtime-receipt is required for execution")
        execute(args.runtime_receipt)
    else:
        report = preflight()
        if args.preflight_output:
            retain(args.preflight_output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
