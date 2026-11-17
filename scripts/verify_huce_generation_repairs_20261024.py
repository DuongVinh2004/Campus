"""Live generation checks against retained, hash-verified HUCE evidence.

This is a component check, not an API/database/retrieval acceptance run. It
resumes the same paid ledger, gateway controls and ordinary evidence guards.
"""
import argparse
import asyncio
import hashlib
import json
import logging
import sys
import time
from datetime import UTC, datetime

from knowledge_platform import ROOT, STATE, checked_path, retain
from run_public_rag import Gateway
from multi_agent_live_resources import restore_paid
from campus247.agent.nodes import async_io, definitions
from campus247.agent.state import AgentState, NormalizedTurn, Route, Terminal, ToolFlowState
from campus247.application.conversation.context import TurnItem
from campus247.application.conversation.history import HistoryContext
from campus247.application.retrieval.semantic_support import SemanticClaimVerifier


class RetainedGateway(Gateway):
    json_mode = True

    async def generate(self, request):
        result = await super().generate(request)
        if request.route_id == "grounded_faq":
            from campus247.application.retrieval.evidence_gate import parse_grounded_claims
            from campus247.application.retrieval.material_support import price_rate_units
            try:
                draft = parse_grounded_claims(result.output_text or "")
                self.proposal_rates.setdefault(request.request_id, []).append({"sha256": hashlib.sha256((result.output_text or "").encode()).hexdigest(),
                    # This script accepts only the fixed public fee fixtures.
                    # Retain parsed claims locally, never provider envelopes,
                    # credentials, prompts, reasoning or arbitrary user input.
                    "public_fixture_claims": [{"text": c.text, "type": c.claim_type} for c in draft.claims],
                    "rates": [[str(value), unit] for c in draft.claims for value, unit in price_rate_units(c.text)]})
            except (ValueError, KeyError, TypeError):
                self.proposal_rates.setdefault(request.request_id, []).append({"invalid_claim_format": True})
        return result

    def _restore_budget(self, snapshot, pending):
        return restore_paid(snapshot, pending)


async def main(repetitions, concurrent=False):
    receipt_path = checked_path(STATE / "independent-sources-20261023T125049141884.json", ROOT)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    doc = next(d for d in receipt["originals"] if d["version_id"].startswith("01a167c6"))
    original = checked_path(ROOT / doc["original_path"], ROOT)
    assert hashlib.sha256(original.read_bytes()).hexdigest() == doc["original_sha256"]
    evidence = next(e for e in doc["evidence"] if e["page_start"] == 2)
    assert hashlib.sha256(evidence["content_text"].encode()).hexdigest() == evidence["content_checksum"]
    candidate = {**evidence, "source_id": "b9e70f30-18ab-7d6d-819b-478e13e8ff00",
        "document_version_id": doc["version_id"], "canonical_uri": doc["canonical_uri"],
        "title": doc["title"], "issuer": "HUCE", "chunk_id": "retained-tuition-page-2",
        "release_id": "01a168c6-dce3-7b72-bcbd-b5797b9452b8", "simulation_label": False}
    cases = json.loads((ROOT / "evals/datasets/huce-repair-hard-20261023.json").read_text(encoding="utf-8"))
    cases += [{"name": "cn_followup", "question": "Cử nhân chính quy K71, năm học 2026-2027.", "followup": True},
        {"name": "cn_k70", "question": "Học phí cử nhân chính quy K70 năm học 2026-2027 ở HUCE?"},
        {"name": "clc_k67", "question": "Học phí kỹ sư chất lượng cao K67 năm học 2026-2027 ở HUCE?"}]
    history = HistoryContext("component-actor", "component-session", (
        TurnItem("1", "user", "Cho biết học phí CNTT của HUCE?"),
        TurnItem("2", "assistant", "Bạn bổ sung khóa học, chương trình và năm học cần tra cứu.")),
        200, "component-fixture")
    gateway = RetainedGateway()
    gateway.proposal_rates = {}
    results = []
    output = checked_path(STATE / ("generation-component-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f") + ".json"), ROOT)
    before = gateway.budget.snapshot()
    async def run_case(iteration, case):
        turn_id = f"component-{iteration}-{case['name']}"
        state = AgentState(NormalizedTurn("component-session", turn_id, "component-actor",
            case["question"], history=history if case.get("followup") else None), route=Route.GROUNDED_FAQ,
            tool_flow=ToolFlowState(candidates=[candidate]))
        started = time.perf_counter()
        result = await async_io.compose_grounded_node(state, gateway, support_threshold=.78,
            claim_verifier=SemanticClaimVerifier(gateway))
        if result.terminal is None:
            result = definitions.evidence_gate_node(result, support_threshold=.78)
            result = definitions.output_guard_node(result)
        item = {"iteration": iteration + 1, "name": case["name"], "question": case["question"],
            "terminal": result.terminal.value if result.terminal else None, "errors": list(result.errors),
            "answer": result.draft.text if result.draft else None,
            "proposal_rates": gateway.proposal_rates.get(turn_id, []),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)}
        results.append(item)
        print(json.dumps({k: v for k, v in item.items() if k != "proposal_rates"}, ensure_ascii=False), flush=True)
    try:
        for iteration in range(repetitions):
            if concurrent:
                pair = [c for c in cases if c["name"] in {"ks_k71", "cn_followup"}]
                await asyncio.gather(*(run_case(iteration, case) for case in pair))
            else:
                for case in cases:
                    await run_case(iteration, case)
    finally:
        retain(output, {"scope": "live_generation_component_with_retained_evidence",
            "concurrent_pair": concurrent,
            "api_database_retrieval_verified": False, "blocking_condition": "postgres.exe blocked by Windows Device Guard",
            "original_sha256": doc["original_sha256"], "evidence_sha256": evidence["content_checksum"],
            "code_sha256": {name: hashlib.sha256(checked_path(ROOT / name, ROOT).read_bytes()).hexdigest()
                for name in ["scripts/verify_huce_generation_repairs_20261024.py",
                    "services/api/src/campus247/agent/nodes/definitions.py",
                    "services/api/src/campus247/agent/nodes/async_io.py",
                    "services/api/src/campus247/application/conversation/generation_policy.py",
                    "services/api/src/campus247/application/retrieval/fee_presentation.py",
                    "services/api/src/campus247/application/retrieval/semantic_support.py"]},
            "budget_before": before, "budget_after": gateway.budget.snapshot(), "results": results})
        gateway.close()
        print(json.dumps({"report": str(output.relative_to(ROOT)), "answered": sum(r["terminal"] == Terminal.ANSWERED.value for r in results),
            "total": len(results)}), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--concurrent", action="store_true", help="Same retained gateway, two simultaneous generation phases")
    args = parser.parse_args()
    asyncio.run(main(args.repetitions, args.concurrent))
