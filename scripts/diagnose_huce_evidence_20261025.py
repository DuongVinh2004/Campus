"""Public-fixture-only component diagnostics; no prompt/provider envelope retained."""
import asyncio
import json
import logging
from datetime import UTC, datetime

from complete_huce_corpus import actors, read
from knowledge_platform import TENANT, components, retain
from prepare_huce_evidence_20261025 import OUT
from run_public_rag import Gateway
from multi_agent_live_resources import restore_paid
from campus247.agent.nodes import async_io, definitions
from campus247.agent.state import AgentState, NormalizedTurn, Route, ToolFlowState
from campus247.application.retrieval.evidence_gate import parse_grounded_claims
from campus247.application.retrieval.semantic_support import SemanticClaimVerifier
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy


class PublicGateway(Gateway):
    json_mode = True

    def _restore_budget(self, snapshot, pending):
        return restore_paid(snapshot, pending)

    async def generate(self, request):
        response = await super().generate(request)
        if request.route_id == "grounded_faq":
            try:
                claims = parse_grounded_claims(response.output_text or "")
                self.public_claims.append([{"text": c.text, "citation_ids": c.citation_ids} for c in claims.claims])
            except (ValueError, TypeError, KeyError):
                self.public_claims.append({"format_invalid": True})
        return response


class Diagnostics(logging.Handler):
    def emit(self, record):
        value = getattr(record, "gate_diagnostic", None)
        if value:
            self.items.append(value)


async def main():
    pool, _, _, runtime = await components()
    _, owner = actors()
    roles = frozenset(r.value for r in owner.roles)
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", owner.subject_id, roles, roles,
        frozenset({"FIT"}), frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "c"*32)
    logger = logging.getLogger("campus247.evidence_gate")
    logger.setLevel(logging.INFO)
    handler = Diagnostics(); handler.items = []
    logger.addHandler(handler)
    gateway = PublicGateway(); gateway.public_claims = []
    results = []
    try:
        for case in read(OUT / "live-cases-01.json"):
            if case["name"] not in {"evidence_civil_k71", "evidence_materials_k71", "evidence_calendar_k68"}:
                continue
            items = await runtime.preview_search(owner, case["question"], context,
                read(OUT / "activation-ready-01.json")["desired"]["release_id"])
            gateway.public_claims = []; handler.items = []
            state = AgentState(NormalizedTurn("public-evidence-component", case["name"], owner.subject_id, case["question"]),
                route=Route.GROUNDED_FAQ, tool_flow=ToolFlowState(candidates=items))
            state = await async_io.compose_grounded_node(state, gateway, context=context, support_threshold=.78,
                claim_verifier=SemanticClaimVerifier(gateway))
            if state.terminal is None:
                state = definitions.evidence_gate_node(state, context=context, support_threshold=.78)
            result = {"name": case["name"], "query": case["question"], "retrieval": items,
                "public_fixture_claims": gateway.public_claims, "gate_diagnostics": handler.items,
                "errors": list(state.errors), "answer": state.draft.text if state.draft else None}
            results.append(result)
            print(json.dumps({k: v for k, v in result.items() if k != "retrieval"}, ensure_ascii=False), flush=True)
        retain(OUT / ("component-diagnostics-" + datetime.now(UTC).strftime("%H%M%S%f") + ".json"), {"cases": results,
            "scope": "Public test fixtures only; component rerun is not API acceptance"})
    finally:
        logger.removeHandler(handler)
        gateway.close()
        await pool.close()


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
