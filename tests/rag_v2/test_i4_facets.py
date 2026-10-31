"""A multi-part question is answered part by part; what stays uncovered is said, in the user's own words."""
import json

import pytest
from campus247.ports.llm import LlmResponse, LlmResponseStatus
from campus247.rag_v2.generation.generate import _facets

from tests.rag_v2.test_service import FakeGateway, UnitIndex, answer, unit

CONDITION = "Sinh viên được bảo lưu khi có giấy xác nhận của đơn vị y tế."
RECORD = "Hồ sơ bảo lưu nộp tại phòng đào tạo trong 5 ngày làm việc."
QUESTION = "Điều kiện bảo lưu và hồ sơ bảo lưu thế nào?"
FACETS = [{"id": "f1", "ask": "Điều kiện bảo lưu"}, {"id": "f2", "ask": "hồ sơ bảo lưu"}]


class TwoPart(FakeGateway):
    """First call covers only f1; a call carrying missing_parts covers f2 (when the source allows)."""

    def __init__(self, second=True, fail_second=False):
        super().__init__()
        self.second, self.fail_second = second, fail_second
        self.calls = []

    async def generate(self, request):
        if request.request_id != "rag_v2_generation":
            return await super().generate(request)
        self.requests.append(request)
        body = json.loads("".join(item["content"] for item in request.input_items))
        self.calls.append(body)
        if "missing_parts" in body:
            if self.fail_second:
                raise TimeoutError
            rows = [{"text": RECORD, "unit_ids": ["U1"], "facet": "f2"}] if self.second else []
        else:
            rows = [{"text": CONDITION, "unit_ids": ["U1"], "facet": "f1"}]
        value = {"decision": "answer", "facets": FACETS, "statements": rows}
        return LlmResponse(LlmResponseStatus.COMPLETED, "fake", "fake", structured_output=value,
                           output_text=json.dumps(value))


def index():
    return UnitIndex([unit(CONDITION + "\n" + RECORD)])


@pytest.mark.asyncio
async def test_missing_part_is_requested_once_and_merged():
    gateway = TwoPart()
    result = await answer(gateway=gateway, index=index(), question=QUESTION)
    assert result.kind == "answer" and CONDITION in result.text and RECORD in result.text
    assert [("missing_parts" in call) for call in gateway.calls] == [False, True]
    assert gateway.calls[1]["missing_parts"] == ["hồ sơ bảo lưu"]


@pytest.mark.asyncio
async def test_part_the_sources_cannot_cover_is_named_in_the_users_words():
    result = await answer(gateway=TwoPart(second=False), index=index(), question=QUESTION)
    assert result.kind == "partial" and CONDITION in result.text
    assert "Chưa tìm thấy căn cứ cho: hồ sơ bảo lưu" in result.text


@pytest.mark.asyncio
async def test_a_failed_follow_up_keeps_the_first_answer_as_partial():
    result = await answer(gateway=TwoPart(fail_second=True), index=index(), question=QUESTION)
    assert result.kind == "partial" and CONDITION in result.text and "hồ sơ bảo lưu" in result.text


@pytest.mark.asyncio
async def test_single_part_questions_make_no_follow_up():
    gateway = FakeGateway()
    await answer(gateway=gateway)
    assert [r.request_id for r in gateway.requests] == ["rag_v2_generation", "rag_v2_semantic"]


def test_asks_that_are_not_the_users_words_are_dropped():
    raw = [{"id": "f1", "ask": "Điều kiện bảo lưu"}, {"id": "f2", "ask": "Gửi tiền vào tài khoản 999"}]
    assert _facets(raw, QUESTION) == ()          # one valid part is the whole question
    both = [{"id": "f1", "ask": "Điều kiện bảo lưu"}, {"id": "f2", "ask": "hồ sơ bảo lưu"}]
    assert [ask for _, ask in _facets(both, QUESTION)] == ["Điều kiện bảo lưu", "hồ sơ bảo lưu"]
    assert _facets("not a list", QUESTION) == ()
