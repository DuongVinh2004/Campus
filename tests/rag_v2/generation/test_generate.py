import asyncio
import json

import pytest
from campus247.infrastructure.llm.egress_policy import EgressPolicy
from campus247.ports.llm import LlmResponse, LlmResponseStatus
from campus247.rag_v2.generation.contacts import contact_map
from campus247.rag_v2.generation.generate import generate_statements
from campus247.rag_v2.outcome.compose import build_outcome
from campus247.rag_v2.types import Understanding, Unit
from campus247.rag_v2.verification.deterministic import check_statement
from campus247.rag_v2.verification.semantic import verify_semantic


def unit(index=1, text="Học phí là 580.500 đồng."):
    return Unit(f"stable-{index}", (f"chunk-{index}",), "doc", "v1", "Nguồn", "fee",
                "clause", "Điều 1", 1, text)


def understanding():
    return Understanding("Học phí?", "học phí", (), None, None, None,
                         "number", (), (), None)


class FakeGateway:
    def __init__(self, output=None, *, structured=None, error=None, delay=0):
        self.output, self.structured = output, structured
        self.error, self.delay = error, delay
        self.requests = []

    async def generate(self, request):
        self.requests.append(request)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return LlmResponse(LlmResponseStatus.COMPLETED, "fake", "fake",
                           output_text=self.output, structured_output=self.structured)


async def run(gateway, units=None, **kwargs):
    return await generate_statements(gateway, "Học phí?", understanding(), units or [unit()],
                                     deadline_ms=kwargs.get("deadline_ms", 1000), max_output_tokens=300)


@pytest.mark.asyncio
async def test_surrounding_text_missing_fields_and_invalid_labels():
    gateway = FakeGateway('Chào bạn! ```json\n' + json.dumps({"statements": [
        {"text": "Học phí là 580.500 đồng.", "unit_ids": ["U1"]},
        {"text": "Không có nguồn"}, {"unit_ids": ["U1"]},
        {"text": "Sai", "unit_ids": ["U9"]},
        {"text": "Sai", "unit_ids": ["stable-1"]},
        {"text": "Sai", "unit_ids": ["U1", "U2"]},
        {"text": "Sai", "unit_ids": "U1"}, None]}) + '\n``` Cảm ơn!')
    result = await run(gateway)
    assert len(result) == 1
    assert result[0].unit_ids == ("stable-1",)
    assert result[0].text == "Học phí là 580.500 đồng."
    request = gateway.requests[0]
    assert request.deadline_ms == 1000 and request.max_output_tokens == 300
    assert request.output_schema and not request.allowed_tools


@pytest.mark.asyncio
async def test_only_twelve_units_and_structured_output():
    gateway = FakeGateway(structured={"statements": [
        {"text": "Nguồn mười hai", "unit_ids": ["U12"]},
        {"text": "Nguồn mười ba", "unit_ids": ["U13"]}]})
    result = await run(gateway, [unit(i, f"Nội dung riêng {i}") for i in range(1, 15)])
    assert [stmt.unit_ids for stmt in result] == [("stable-12",)]
    payload = json.loads("".join(item["content"] for item in gateway.requests[0].input_items))
    assert len(payload["sources"]) == 12
    assert payload["sources"][0]["label"] == "[U1]"


@pytest.mark.asyncio
@pytest.mark.parametrize("output", [None, "", "broken", "{}", '{"statements":null}',
                                    '{"statements":[{"text":"x","unit_ids":[{}]}]}'])
async def test_malformed_drafts_are_empty(output):
    assert await run(FakeGateway(output)) == []


@pytest.mark.asyncio
async def test_no_sources_no_model_call():
    gateway = FakeGateway()
    assert await generate_statements(gateway, "?", understanding(), [],
                                     deadline_ms=100, max_output_tokens=100) == []
    assert not gateway.requests


@pytest.mark.asyncio
async def test_contacts_do_not_reach_egress_and_unknown_markers_are_dropped():
    source = unit(text="Liên hệ bộ phận: synthetic-office@huce.edu.vn, 0912345678; IP 10.1.2.3; SV123456.")
    markers = contact_map([source])
    marker = next(label for label, value in markers.items() if "@" in value)
    gateway = FakeGateway(structured={"statements": [
        {"text": f"Liên hệ {marker}.", "unit_ids": ["U1"]},
        {"text": "Liên hệ PUBLIC_CONTACT_EMAIL_UNKNOWN.", "unit_ids": ["U1"]}]})
    result = await run(gateway, [source])
    assert len(result) == 1 and marker in result[0].text
    request = gateway.requests[0]
    payload = {"purpose": "FAQ_ANSWERING", "model": "fake", "messages": [
        {"role": "system", "content": request.system_instructions}, *request.input_items],
        "max_tokens": request.max_output_tokens}
    assert EgressPolicy().validate_and_minimize(payload)
    for value in markers.values():
        assert value not in json.dumps(payload)


@pytest.mark.asyncio
async def test_cross_unit_contact_marker_cannot_be_cited():
    sources = [unit(1, "Liên hệ synthetic-office@huce.edu.vn."), unit(2, "Thông tin khác.")]
    marker = next(iter(contact_map(sources)))
    gateway = FakeGateway(structured={"statements": [{"text": marker, "unit_ids": ["U2"]}]})
    assert await run(gateway, sources) == []


@pytest.mark.asyncio
async def test_generation_timeout_propagates_for_infrastructure_outcome():
    with pytest.raises(TimeoutError):
        await run(FakeGateway(delay=1), deadline_ms=1)


@pytest.mark.asyncio
@pytest.mark.parametrize("supported", [True, False])
async def test_contact_pipeline_generates_checks_restores_or_refuses(supported):
    source = unit(text="Liên hệ synthetic-office@huce.edu.vn.")
    marker = next(iter(contact_map([source])))

    class PipelineGateway:
        def __init__(self):
            self.requests = []

        async def generate(self, request):
            self.requests.append(request)
            EgressPolicy().validate_and_minimize({
                "purpose": "FAQ_ANSWERING", "model": "fake", "messages": [
                    {"role": "system", "content": request.system_instructions}, *request.input_items]})
            output = ({"statements": [{"text": f"Liên hệ {marker}.", "unit_ids": ["U1"]}]}
                      if len(self.requests) == 1 else {"verdicts": [{"i": 0, "supported": supported}]})
            return LlmResponse(LlmResponseStatus.COMPLETED, "fake", "fake", structured_output=output)

    gateway = PipelineGateway()
    statements = await run(gateway, [source])
    units = {source.unit_id: source}
    verdicts = [check_statement(stmt, units) for stmt in statements]
    semantic = await verify_semantic(gateway, statements, units, "Liên hệ?", deadline_ms=1000)
    result = build_outcome(understanding(), verdicts, units, semantic_results=semantic)
    assert len(gateway.requests) == 2
    assert result.kind == ("answer" if supported else "refuse")
    if supported:
        assert result.text == source.text and result.citations[0].quote == source.text
    else:
        assert result.reason == "unverified" and not result.citations
