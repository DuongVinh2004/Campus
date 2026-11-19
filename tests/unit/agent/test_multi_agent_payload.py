"""Keep original evidence while excluding server authorization from model input."""
import json

import pytest

from campus247.infrastructure.llm.egress_policy import EgressPolicy
from tests.unit.agent.test_multi_agent_integrated import SOURCE, row, setup


@pytest.mark.asyncio
async def test_worker_payload_keeps_sources_and_server_side_bindings(tmp_path):
    workflow, turn, context, _, model, rows = setup(tmp_path)
    rows[:] = [row(SOURCE + " Public source passage." * 100) for _ in range(4)]
    await workflow.arun(turn, retrieval_context=context)
    reports = [request for request in model.calls
               if request.route_id in {"multi_research_report", "multi_verifier_coverage"}]
    assert len(reports) == 2
    for request in reports:
        content = request.input_items[0]["content"]
        data = json.loads(content)["untrusted_data"]
        assert "binding" not in data["task"]
        assert ["".join(span["text"] for span in evidence["original_spans"])
                for evidence in data["evidence"]] == [value["content_text"] for value in rows]
        EgressPolicy().validate_and_minimize({"purpose": "FAQ_ANSWERING",
            "model": "deepseek-flash", "messages": [{"role": "user", "content": content}]})
    stored = workflow.store.tasks(turn.turn_id)
    assert all(value["spec"]["binding"]["scope"]["actor_id"] == turn.user_id for value in stored)
