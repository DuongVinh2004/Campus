import asyncio
import json

import pytest
from campus247.infrastructure.llm.egress_policy import EgressPolicy
from campus247.ports.llm import LlmResponse, LlmResponseStatus
from campus247.rag_v2.generation.contacts import contact_map
from campus247.rag_v2.types import Statement, Unit
from campus247.rag_v2.verification.semantic import verify_semantic

SOURCE = Unit("a", ("c",), "d", "v", "Nguồn", "policy", "clause", "Điều 1", 1,
              "Liên hệ synthetic-office@huce.edu.vn hoặc 0912345678.")


class FakeGateway:
    def __init__(self, value=None, error=None, delay=0, status=LlmResponseStatus.COMPLETED):
        self.value, self.error, self.delay, self.status = value, error, delay, status
        self.requests = []

    async def generate(self, request):
        self.requests.append(request)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return LlmResponse(self.status, "fake", "fake", structured_output=self.value)


@pytest.mark.asyncio
async def test_one_call_index_order_and_no_completeness_gate():
    gateway = FakeGateway({"verdicts": [{"i": 1, "supported": False}, {"i": 0, "supported": True}]})
    statements = [Statement("Liên hệ bộ phận.", ("a",)), Statement("Thông tin khác.", ("a",))]
    assert await verify_semantic(gateway, statements, {"a": SOURCE}, "Liên hệ?", deadline_ms=1000) == [True, False]
    assert len(gateway.requests) == 1
    request = gateway.requests[0]
    assert "answers_question" not in request.system_instructions
    assert "hỗ trợ trực tiếp" in request.system_instructions
    assert request.output_schema and not request.allowed_tools


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [
    {}, {"verdicts": []}, {"verdicts": [{"i": 0, "supported": "true"}]},
    {"verdicts": [{"i": True, "supported": True}]},
    {"verdicts": [{"i": 2, "supported": True}]},
    {"verdicts": [{"i": 0, "supported": True, "extra": "x"}]},
    {"verdicts": [{"i": 0, "supported": True}], "answers_question": True},
])
async def test_invalid_schema_returns_none(value):
    assert await verify_semantic(FakeGateway(value), [Statement("x", ("a",))],
                                 {"a": SOURCE}, "?", deadline_ms=100) is None


@pytest.mark.asyncio
async def test_duplicates_and_missing_index_are_not_success():
    gateway = FakeGateway({"verdicts": [{"i": 0, "supported": True}, {"i": 0, "supported": True}]})
    assert await verify_semantic(gateway, [Statement("x", ("a",))] * 2,
                                 {"a": SOURCE}, "?", deadline_ms=100) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("kwargs", [{"error": RuntimeError("provider failed")},
                                       {"delay": 1}, {"status": LlmResponseStatus.FAILED}])
async def test_provider_errors_and_timeout_return_none(kwargs):
    assert await verify_semantic(FakeGateway(**kwargs), [Statement("x", ("a",))],
                                 {"a": SOURCE}, "?", deadline_ms=1) is None


@pytest.mark.asyncio
async def test_contacts_minimized_in_sources_and_statements():
    gateway = FakeGateway({"verdicts": [{"i": 0, "supported": True}]})
    assert await verify_semantic(gateway, [Statement(SOURCE.text, ("a",))],
                                 {"a": SOURCE}, "Liên hệ?", deadline_ms=100) == [True]
    request = gateway.requests[0]
    payload = {"purpose": "FAQ_ANSWERING", "model": "fake", "messages": [
        {"role": "system", "content": request.system_instructions}, *request.input_items]}
    assert EgressPolicy().validate_and_minimize(payload)
    text = json.dumps(payload)
    for value in contact_map([SOURCE]).values():
        assert value not in text
    assert "PUBLIC_CONTACT_" in text


@pytest.mark.asyncio
async def test_empty_or_invalid_input_avoids_provider():
    gateway = FakeGateway()
    assert await verify_semantic(gateway, [], {}, "?", deadline_ms=1) == []
    assert await verify_semantic(gateway, [Statement("x", ("missing",))], {}, "?", deadline_ms=1) is None
    assert await verify_semantic(gateway, [Statement("x", ("a",))], {"a": SOURCE}, "?", deadline_ms=0) is None
    assert not gateway.requests
