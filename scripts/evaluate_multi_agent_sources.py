"""48-case canonical source/readback regression without paid/native inference.

This is lexical source validation, not live generation, neural retrieval, or an
architecture comparison. The dev gold and prior neural reports remain unchanged.
"""
import argparse
import asyncio
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "services/api/src"), str(ROOT / "scripts")]
from multi_agent_workspace import STATE, checked, retain


async def evaluate():
    from campus247.agent.state import AgentState, NormalizedTurn
    from campus247.application.conversation.context import TurnItem
    from campus247.application.conversation.history import HistoryContext
    from campus247.application.multi_agent.contracts import MultiAgentPolicy
    from campus247.application.single_agent.controller import EvidenceController
    from campus247.application.single_agent.resources import RunResources
    from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
    from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore
    from scripts.public_rag_retrieval import load_public_hybrid_store
    from evaluate_certificate_rag import paid_snapshot, native_snapshot
    dataset_path = ROOT / "evals/datasets/certificate-development-20261013.json"
    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    store = PublicKnowledgeStore(ROOT / "data/huce-public-20261013", tenant_id="huce-local-public", campus_id="HUCE",
        faq_directory=ROOT / "data/huce-faq-20261013")
    hybrid = load_public_hybrid_store(ROOT / "data/huce-public-20261013", tenant_id="huce-local-public", campus_id="HUCE",
        faq_directory=ROOT / "data/huce-faq-20261013")  # construction reads only
    source_ids = {ref: next(row["chunk_id"] for row in store.rows if row["page_start"] == page and row["canonical_uri"] == data["sources"][ref]["url"])
                  for ref, page in (("catalog", 35), ("procedure", 39))}
    paid_before, native_before = paid_snapshot(), native_snapshot()
    results = []
    for case in data["cases"]:
        trace, started = [], time.monotonic()
        context = RetrievalContext(AuthorizedScope("huce-local-public", "HUCE", "source-eval",
            frozenset({"STUDENT"}), frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})),
            "vi", datetime.now(timezone.utc), SimulationPolicy.DENY, "1"*32)
        history = HistoryContext("source-eval", case["id"], tuple(TurnItem(str(index), "user", row["content"], True)
            for index, row in enumerate(case["history"])), 0, "source-regression")
        turn = NormalizedTurn(case["id"], case["id"], "source-eval", case["question"], history=history)
        state = AgentState(turn, trusted_context_ref=context.trace_id)
        tools = EvidenceController(search=store.search, reader=store, gateway=None, resources=RunResources(MultiAgentPolicy()),
            current_context=lambda: context, checkpoint=lambda _: None,
            event=lambda tool, status, duration, value: trace.append({"tool": tool, "status": status, "duration_ms": duration, **value}),
            support_threshold=.78, claim_verifier=None)
        try:
            await tools.search_and_read(state, case["question"])
            found = set(tools.evidence)
            required = [source_ids[ref] for ref in case["source_refs"]]
            covered = all(key in found for key in required) if required else None
            result = {"id": case["id"], "question": case["question"], "required_source_coverage": covered,
                "source_check_verdict": "hash_and_eligibility_verified", "source_ids": sorted(found), "failure": None,
                "generation": "not_verified_insufficient_paid_headroom", "expected_behavior": case["expected_behavior"]}
        except Exception as failure:
            result = {"id": case["id"], "question": case["question"], "required_source_coverage": False if case["source_refs"] else None,
                      "failure": getattr(failure, "code", type(failure).__name__), "generation": "not_verified"}
        result.update(trace=trace, latency_ms=round((time.monotonic()-started)*1000, 2))
        results.append(result)
    after, native_after = paid_snapshot(), native_snapshot()
    if after != paid_before or native_after != native_before:
        raise RuntimeError("ledger changed during source-only run; retain evidence without attribution")
    return {"mode": "source_only_actual_canonical_lexical", "fresh_live_multi_agent": False,
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(), "index_fingerprint": hybrid.fingerprint,
        "policy_fingerprint": MultiAgentPolicy().fingerprint, "provider_calls": 0, "native_inference": 0, "cost_usd": 0,
        "paid_before": paid_before, "paid_after": after, "native_before": native_before, "native_after": native_after,
        "source_covered": sum(row["required_source_coverage"] is True for row in results),
        "source_cases": sum(row["required_source_coverage"] is not None for row in results), "results": results,
        "limits": "No model planning/generation/semantic verification or neural retrieval. Source presence and hashes do not prove answer correctness/coverage. Development regression, not held-out or comparison. No gold/threshold edits."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = checked(args.output, STATE)
    if output.exists():
        raise FileExistsError("choose a new output name")
    report = asyncio.run(evaluate())
    retain(output, report)
    print(json.dumps({"source_covered": report["source_covered"], "source_cases": report["source_cases"],
                      "provider_calls": 0, "generation": "not_verified"}))
