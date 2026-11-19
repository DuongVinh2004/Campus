"""Server evidence handles avoid false identifier matches without hiding source PII."""
import json
from dataclasses import replace

import pytest

from campus247.agent.state import Terminal
from campus247.infrastructure.llm.egress_policy import EgressPolicy
from tests.unit.agent.test_multi_agent_integrated import ScriptedModel, setup


class PolicyModel(ScriptedModel):
    async def generate(self, request):
        if request.route_id in {"multi_research_report", "multi_verifier_coverage"}:
            EgressPolicy().validate_and_minimize({"purpose": "FAQ_ANSWERING", "messages": list(request.input_items)})
        return await super().generate(request)


@pytest.mark.asyncio
async def test_digit_run_in_internal_uuid_does_not_leave_server_but_original_refs_remain(tmp_path):
    workflow, turn, context, reader, model, rows = setup(tmp_path, model=PolicyModel())
    original = "aaaaaaaa-aaaa-7aaa-8aaa-123456789012"
    rows[0]["chunk_id"] = original
    result = await workflow.arun(turn, retrieval_context=context)
    assert result.terminal == Terminal.ANSWERED
    reports = [r for r in model.calls if r.route_id in {"multi_research_report", "multi_verifier_coverage"}]
    assert reports and all(original not in json.dumps(r.input_items) for r in reports)
    record = workflow.store.get(turn.turn_id, turn.user_id, turn.session_id)
    assert record["controller"]["evidence_refs"][0]["chunk_id"] == original
    assert reader.reads


@pytest.mark.asyncio
async def test_real_phone_in_source_is_still_rejected(tmp_path):
    workflow, turn, context, _, _, rows = setup(tmp_path, model=PolicyModel())
    import hashlib
    rows[0]["content_text"] += " Liên hệ 0987654321."
    rows[0]["quote_span_hash"] = hashlib.sha256(rows[0]["content_text"].encode()).hexdigest()
    result = await workflow.arun(turn, retrieval_context=context)
    assert result.terminal == Terminal.ABSTAINED
    assert "AI_AGENT_MODEL_REQUEST_REJECTED" in result.errors


@pytest.mark.asyncio
async def test_model_cannot_invent_an_evidence_handle(tmp_path):
    class ForgedModel(PolicyModel):
        async def generate(self, request):
            response = await super().generate(request)
            if request.route_id == "multi_research_report":
                value = json.loads(response.output_text)
                value["coverage"][0]["supports"][0]["evidence_id"] = "EV-FOREIGN"
                return replace(response, output_text=json.dumps(value))
            return response
    workflow, turn, context, _, _, _ = setup(tmp_path, model=ForgedModel())
    result = await workflow.arun(turn, retrieval_context=context)
    assert result.terminal == Terminal.SAFE_FAILURE
    assert "AI_AGENT_COVERAGE_INVALID_PROVENANCE" in result.errors
