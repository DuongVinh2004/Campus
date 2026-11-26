"""A multi-part question is answered part by part; what stays uncovered is said, in the user's own words."""
import json
from dataclasses import replace

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


DEADLINE = "Thời gian tiếp nhận hồ sơ: từ ngày 29/9/2026 đến hết ngày 20/10/2026."


class FocusIndex(UnitIndex):
    """The first search (the whole question) finds only the condition; a search with the missing part's words finds the date."""

    def lexical(self, query, limit, *, allowed=None):
        from campus247.rag_v2.understanding.normalize import fold
        words = fold(query).split()
        wanted = ["b" * 16] if "han" in words and "luu" not in words else ["a" * 16]
        return [(uid, 1.0) for uid in wanted if uid in allowed][:limit]


class Deadline(FakeGateway):
    def __init__(self):
        super().__init__()
        self.calls = []

    async def generate(self, request):
        if request.request_id != "rag_v2_generation":
            return await super().generate(request)
        body = json.loads("".join(item["content"] for item in request.input_items))
        self.calls.append(body)
        facets = [{"id": "f1", "ask": "Điều kiện bảo lưu"}, {"id": "f2", "ask": "hạn chót nộp là bao giờ"}]
        if "missing_parts" in body:
            label = next(s["label"].strip("[]") for s in body["sources"] if "20/10/2026" in s["text"])
            rows = [{"text": "Thời gian tiếp nhận hồ sơ đến hết ngày 20/10/2026.", "unit_ids": [label], "facet": "f2"}]
        else:
            rows = [{"text": CONDITION, "unit_ids": ["U1"], "facet": "f1"}]
        value = {"decision": "answer", "facets": facets, "statements": rows}
        return LlmResponse(LlmResponseStatus.COMPLETED, "fake", "fake", structured_output=value, output_text=json.dumps(value))


@pytest.mark.asyncio
async def test_the_follow_up_looks_up_evidence_for_the_missing_part_within_the_same_documents():
    from campus247.rag_v2.types import Fact, Scope
    condition, deadline = unit(CONDITION, uid="a" * 16), unit(DEADLINE, uid="b" * 16)
    other = replace(unit("Hạn nộp học phí khác: 01/01/2027.", uid="c" * 16), document_id="other-doc")
    fact = Fact("f" * 16, "deadline", "Thời gian tiếp nhận hồ sơ", "20/10/2026", "b" * 16, DEADLINE, Scope(), {"date_role": "end"})
    gateway = Deadline()
    result = await answer(gateway=gateway, index=FocusIndex([condition, deadline, other]),
                          question="Điều kiện bảo lưu và hạn chót nộp là bao giờ?", facts=(fact,))
    assert result.kind == "answer" and "20/10/2026" in result.text and CONDITION in result.text
    first, second = gateway.calls
    assert not any("20/10/2026" in s["text"] for s in first["sources"])             # the first search missed the date
    assert any("20/10/2026" in s["text"] for s in second["sources"])                # the follow-up found it
    assert not any("01/01/2027" in s["text"] for s in second["sources"])            # never from another document


class AskBack(FakeGateway):
    """Answers "clarify" without naming a missing part, then (if asked again with subject_named) answers from the source."""

    def __init__(self, answer_on_second=True):
        super().__init__()
        self.answer_on_second, self.calls = answer_on_second, []

    async def generate(self, request):
        if request.request_id != "rag_v2_generation":
            return await super().generate(request)
        body = json.loads("".join(item["content"] for item in request.input_items))
        self.calls.append(body)
        if body.get("subject_named") and self.answer_on_second:
            value = {"decision": "answer", "statements": [{"text": CONDITION, "unit_ids": ["U1"]}]}
        else:
            value = {"decision": "clarify", "missing_slots": [], "statements": []}
        return LlmResponse(LlmResponseStatus.COMPLETED, "fake", "fake", structured_output=value, output_text=json.dumps(value))


@pytest.mark.asyncio
async def test_a_topicless_ask_back_on_a_question_that_names_its_subject_is_retried_once():
    gateway = AskBack()
    result = await answer(gateway=gateway, index=index(), question="Nếu em bị ốm thì điều kiện bảo lưu của sinh viên là gì và nộp ở đâu ạ?")
    assert result.kind in {"answer", "partial"} and CONDITION in result.text
    assert [bool(call.get("subject_named")) for call in gateway.calls] == [False, True]


@pytest.mark.asyncio
async def test_a_pronoun_only_question_still_gets_the_topic_ask_back_without_a_retry():
    from campus247.rag_v2.service import vague_reference
    assert vague_reference("Việc này thì sao ạ?") and not vague_reference("Điều kiện bảo lưu là gì?")
    gateway = AskBack(answer_on_second=False)
    result = await answer(gateway=gateway, index=index(), question="Vụ đó thì sao ạ?")
    assert result.kind == "clarify" and len(gateway.calls) <= 1


def test_a_when_part_counts_as_answered_only_by_a_statement_that_says_when():
    from types import SimpleNamespace
    from campus247.rag_v2.service import _uncovered
    facets = (("f1", "giấy tờ gì"), ("f2", "hạn chót nộp là bao giờ"))
    verdict = lambda text: SimpleNamespace(passed=True, statement=SimpleNamespace(text=text))
    undated = [verdict("Nộp đơn và giấy xác nhận."), verdict("Chỉ cần nộp hồ sơ 01 lần cho đến khi kết thúc khóa học.")]
    assert _uncovered(facets, ["f1", "f2"], undated) == ["hạn chót nộp là bao giờ"]
    dated = [verdict("Nộp đơn và giấy xác nhận."), verdict("Thời gian tiếp nhận hồ sơ đến hết ngày 20/10/2026.")]
    assert _uncovered(facets, ["f1", "f2"], dated) == []
    assert _uncovered((("f1", "giấy tờ gì"),), ["f1"], undated[:1]) == []            # other parts unchanged
