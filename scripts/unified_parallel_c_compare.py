"""Matched single graph/selected multi control-flow evaluation with local fakes."""
import argparse
import asyncio
from collections import Counter
from dataclasses import asdict
import json
import re
import sys
import time

sys.dont_write_bytecode = True
from unified_parallel_c_preserve import ROOT, STATE, checked, manifest, retain, sha


async def run(number):
    sys.path[:0] = [str(ROOT), str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")]
    from campus247.agent.graph import CampusAgentWorkflow
    from campus247.agent.state import Terminal
    from campus247.application.conversation.stream_result import prepare_chat_result
    from tests.unit.agent.test_multi_agent_integrated import setup, ScriptedModel, SOURCE
    target = checked(STATE / "fixtures" / ("matched-comparison-" + number))
    target.mkdir(exist_ok=False)
    source_before = manifest()
    results = []
    # All expected material facts come from this literal synthetic source,
    # independent of either model response. No result determines its own gold.
    gold = {"source_sha256": sha(SOURCE.encode()), "fee": "50.000", "forbidden_fee": "90.000",
            "scope": "fee only, not an official institutional fee", "facts_source": "tests/unit/agent/test_multi_agent_integrated.py::SOURCE"}
    for condition in ["current_source", "missing_source", "wrong_numeric_claim"]:
        case_dir = checked(target / condition)
        case_dir.mkdir(exist_ok=False)
        multi_model = ScriptedModel(false_claim=condition == "wrong_numeric_claim")
        multi, turn, context, reader, _, rows = setup(case_dir, model=multi_model)
        async def search(query, scope):
            if scope != context:
                raise ValueError("scope mismatch")
            return [] if condition == "missing_source" else rows
        multi._context_search_fn = search
        simple_model = ScriptedModel(false_claim=condition == "wrong_numeric_claim")
        simple = CampusAgentWorkflow(context_search_fn=search, llm_gateway=simple_model,
                                    require_retrieval_context=True, evidence_support_threshold=.78)
        observations = {}
        for mode, workflow, model in [("single_graph", simple, simple_model), ("selected_multi", multi, multi_model)]:
            started = time.monotonic()
            result = await workflow.arun(turn, retrieval_context=context)
            latency = (time.monotonic() - started) * 1000
            text = result.draft.text if result.draft else ""
            final = prepare_chat_result(result)
            should_answer = condition == "current_source"
            gates = {"expected_answer_or_abstention": (result.terminal == Terminal.ANSWERED) == should_answer,
                     "wrong_fee_not_published": gold["forbidden_fee"] not in text,
                     "gold_fee_present_if_answered": gold["fee"] in text if should_answer else True,
                     "citation_present_if_answered": bool(final.citations) if should_answer else True}
            observation = {"terminal": str(result.terminal), "latency_ms": latency,
                           "fake_model_dispatches": len(model.calls),
                           "routes": dict(Counter(call.route_id for call in model.calls)),
                           "material_gates": gates, "passed": all(gates.values()), "model_cost_usd": None,
                           "error_codes": list(result.errors), "human_usefulness_verified": False}
            if mode == "selected_multi":
                record = multi.store.get(turn.turn_id, turn.user_id, turn.session_id)
                observation["durable_usage"] = record["usage"]
                observation["task_count"] = len(multi.store.tasks(turn.turn_id))
                observation["source_reads"] = len(reader.reads)
                observation["durable_dispatch_count_matches_fake"] = record["usage"]["model_calls"] == len(model.calls)
                observation["budget_caps"] = asdict(multi.policy)
            observations[mode] = observation
        results.append({"id": "C-MATCH-" + condition, "condition": condition, "observations": observations})
    report = {"protocol": "unified-c-matched-control-flow.v1", "gold": gold, "cases": results,
              "source_stable": source_before == manifest(), "paid_provider_calls": 0,
              "source_hashes": source_before, "staff031_035_prepare_only": "separately tested actual case consumer; no model staff-outcome generation claimed",
              "expert_blind_review": "not_run", "human_usefulness_verified": False, "UNI_045_acceptance": "pending",
              "limitations": ["Three synthetic cases and scripted model ports measure control flow, not model intelligence or real user benefit",
                  "Single graph and multi share application guardrails but multi adds durable source rereads/coverage/dispatch",
                  "Latency includes SQLite and local scheduling, not a serving/production estimate",
                  "No statistical p95/cost claim; model USD unobserved", "No code/policy fan-out change based on this sample"]}
    retain(target / "report.json", report)
    print(json.dumps({"source_stable": report["source_stable"], "cases": results, "acceptance": "pending"}, ensure_ascii=False))
    if not all(obs["passed"] for case in results for obs in case["observations"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("number")
    args = parser.parse_args()
    if re.fullmatch(r"[0-9]{2}", args.number) is None:
        raise ValueError("fresh exact attempt required")
    asyncio.run(run(args.number))
