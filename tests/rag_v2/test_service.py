"""Synthetic source spans checked by code; no HTTP, credentials or runtime."""
import asyncio
import json
from dataclasses import replace

import pytest
from campus247.ports.llm import LlmResponse, LlmResponseStatus
from campus247.rag_v2.service import RagV2Service
from campus247.rag_v2.types import Fact, Scope, Unit

QUESTION = "Điều kiện bảo lưu là gì?"
TEXT = "Sinh viên nộp hồ sơ bảo lưu tại phòng đào tạo."


def unit(text=TEXT, uid="a" * 16, scope=None):
    return Unit(uid, ("chunk",), "doc", "version", "Quy chế", "quy_che", "clause", "Điều 1", 1,
                text, scope=scope or Scope())


class UnitIndex:
    def __init__(self, units=None):
        self.units = {u.unit_id: u for u in ([unit()] if units is None else units)}
        self.seen = []

    def get(self, uid):
        return self.units.get(uid)

    def all_ids(self):
        return tuple(self.units)

    def lexical(self, query, limit, *, allowed=None):
        self.seen.append(allowed)
        return [(uid, 1.0) for uid in self.units if uid in allowed][:limit]

    async def vector(self, query, limit, *, allowed=None):
        return self.lexical(query, limit, allowed=allowed)


class Reranker:
    def __init__(self, *, error=False, delay=0):
        self.error, self.delay = error, delay
        self.calls = []

    async def rerank(self, query, texts, *, deadline_s):
        self.calls.append((list(texts), deadline_s))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise TimeoutError
        return [2.0] * len(texts)


class FakeGateway:
    def __init__(self, drafts=None, supported=True, fail=None, delay=0):
        self.drafts = drafts if drafts is not None else [[TEXT]]
        self.supported, self.fail, self.delay = supported, fail, delay
        self.requests = []
        self.generated = 0

    async def generate(self, request):
        self.requests.append(request)
        if request.request_id == self.fail:
            raise RuntimeError("PRIVATE_PROVIDER_ERROR user@example.test")
        if self.delay and request.request_id == "rag_v2_generation":
            await asyncio.sleep(self.delay)
        if request.request_id == "rag_v2_generation":
            rows = self.drafts[min(self.generated, len(self.drafts) - 1)]
            self.generated += 1
            value = {"statements": [{"text": text, "unit_ids": ["U1"]} for text in rows]}
        elif request.request_id == "rag_v2_semantic":
            payload = json.loads("".join(item["content"] for item in request.input_items))
            value = {"verdicts": [{"i": i, "supported": self.supported} for i in range(len(payload["statements"]))]}
        else:
            value = {"severity": "normal", "is_crisis": False, "route": "grounded_faq"}
        return LlmResponse(LlmResponseStatus.COMPLETED, "fake", "fake", structured_output=value,
                           output_text=json.dumps(value))


async def answer(*, gateway=None, index=None, reranker=None, question=QUESTION, facts=(), **kwargs):
    return await RagV2Service(facts).answer(question, (), gateway=gateway or FakeGateway(),
        index=index or UnitIndex(), reranker=reranker or Reranker(), embed=None, **kwargs)


@pytest.mark.asyncio
async def test_complete_answer_semantic_once_and_original_citation(caplog):
    gateway = FakeGateway()
    result = await answer(gateway=gateway)
    assert result.kind == "answer" and result.text == TEXT
    assert [r.request_id for r in gateway.requests] == ["rag_v2_generation", "rag_v2_semantic"]
    assert result.citations[0].quote == TEXT
    assert result.citations[0].quote in unit().text
    assert result.trace["outcome_kind"] == "answer" and result.trace["candidate_count"] == 1
    assert "rag_v2_trace" in caplog.text and QUESTION not in caplog.text and TEXT not in caplog.text


@pytest.mark.asyncio
async def test_partial_keeps_only_verified_statement_without_regenerating():
    gateway = FakeGateway(drafts=[[TEXT, "Sinh viên phải nộp 999 hồ sơ."]])
    result = await answer(gateway=gateway)
    assert result.kind == "partial" and result.partial_note
    assert len(result.statements) == 1 and "999" not in result.text
    assert gateway.generated == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(("question", "kind", "reason"), [
    ("Học phí bao nhiêu?", "clarify", None), ("Thời tiết hôm nay?", "refuse", "out_of_scope")])
async def test_early_outcomes_never_retrieve_or_generate(question, kind, reason):
    gateway, index, reranker = FakeGateway(), UnitIndex(), Reranker()
    result = await answer(question=question, gateway=gateway, index=index, reranker=reranker)
    assert (result.kind, result.reason) == (kind, reason)
    assert not gateway.requests and not index.seen and not reranker.calls


@pytest.mark.asyncio
async def test_no_source():
    gateway = FakeGateway()
    result = await answer(index=UnitIndex([]), gateway=gateway)
    assert result.reason == "no_source" and not gateway.requests and not result.citations


@pytest.mark.asyncio
async def test_semantic_rejection_is_unverified_and_never_repaired():
    gateway = FakeGateway(supported=False)
    result = await answer(gateway=gateway)
    assert result.reason == "unverified" and not result.citations and gateway.generated == 1
    assert result.trace["statement_rejections"][0]["reasons"] == ["SEMANTIC_UNSUPPORTED"]


@pytest.mark.asyncio
async def test_one_repair_with_finite_codes_only():
    gateway = FakeGateway(drafts=[["Nộp 999 hồ sơ."], [TEXT]])
    result = await answer(gateway=gateway)
    assert result.kind == "answer" and gateway.generated == 2
    retry = gateway.requests[1]
    assert "NUMBER_NOT_IN_SOURCE" in retry.system_instructions and "999" not in retry.system_instructions
    assert len([r for r in gateway.requests if r.request_id == "rag_v2_semantic"]) == 1


@pytest.mark.asyncio
async def test_second_invalid_generation_refuses_without_third_attempt():
    gateway = FakeGateway(drafts=[["Nộp 999 hồ sơ."]])
    result = await answer(gateway=gateway)
    assert result.reason == "unverified" and gateway.generated == 2 and len(gateway.requests) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["rag_v2_generation", "rag_v2_semantic"])
async def test_gateway_failure_becomes_transient_with_retry_hint(stage):
    result = await answer(gateway=FakeGateway(fail=stage))
    assert result.kind == "transient_error" and result.retry_hint and not result.citations
    assert "PRIVATE" not in str(result) and "@" not in str(result.trace)


@pytest.mark.asyncio
async def test_failed_provider_response_is_transient():
    class Failed(FakeGateway):
        async def generate(self, request):
            return LlmResponse(LlmResponseStatus.FAILED, "fake", "fake")
    assert (await answer(gateway=Failed())).kind == "transient_error"


@pytest.mark.asyncio
async def test_rerank_timeout_keeps_rrf_and_still_answers():
    result = await answer(reranker=Reranker(error=True))
    assert result.kind == "answer" and result.trace["rerank_scores"] == []


@pytest.mark.asyncio
async def test_generation_deadline_is_handled_not_blank():
    result = await asyncio.wait_for(answer(gateway=FakeGateway(delay=3), deadline_s=.03), .5)
    assert result.kind == "transient_error" and result.text and result.retry_hint


@pytest.mark.asyncio
async def test_cancellation_propagates():
    class Cancel(FakeGateway):
        async def generate(self, request):
            raise asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await answer(gateway=Cancel())


@pytest.mark.asyncio
@pytest.mark.parametrize(("kind", "subject", "quote", "question", "scope"), [
    ("fee", "học phí đại trà", "Học phí đại trà K64 năm học 2026-2027: 580.500 đồng/tín chỉ.",
     "Học phí đại trà K64 năm học 2026-2027 bao nhiêu?",
     Scope(cohorts=("K64",), programs=("đại trà",), academic_years=("2026-2027",))),
    ("contact", "phòng đào tạo", "Phòng đào tạo: daotao@huce.edu.vn", "Email phòng đào tạo?", Scope()),
    ("deadline", "nộp hồ sơ học bổng", "Nộp hồ sơ học bổng năm học 2026-2027 trước 20/10/2026.",
     "Hạn nộp hồ sơ học bổng năm học 2026-2027?", Scope(academic_years=("2026-2027",))),
    ("prerequisite", "123456", "123456 có học phần tiên quyết: 654321.",
     "Học phần tiên quyết của 123456 là gì?", Scope()),
])
async def test_typed_facts_bypass_models_but_preserve_verbatim_quote(kind, subject, quote, question, scope):
    source = unit(quote, scope=scope)
    value = {"fee": "580.500", "contact": "daotao@huce.edu.vn", "deadline": "20/10/2026",
             "prerequisite": "654321"}[kind]
    fact = Fact("fact", kind, subject, value, source.unit_id, quote, scope,
                {"contact_type": "email"} if kind == "contact" else {})
    gateway, reranker = FakeGateway(), Reranker()
    result = await answer(question=question, index=UnitIndex([source]), gateway=gateway,
                          reranker=reranker, facts=(fact,))
    assert result.kind == "answer" and result.statements[0].text == quote
    assert result.citations[0].quote == fact.quote and value in result.citations[0].quote
    assert not gateway.requests and not reranker.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["subject", "scope", "value", "quote"])
async def test_nonmatching_fact_cannot_bypass_normal_checks(change):
    quote = "Phòng đào tạo nhận hồ sơ."
    source = unit(quote)
    fact = Fact("f", "contact", "phòng đào tạo", "hồ sơ", source.unit_id, quote)
    changes = {"subject": {"subject": "phòng tài vụ"}, "scope": {"scope": Scope(cohorts=("K99",))},
               "value": {"value": "bịa"}, "quote": {"quote": "phát biểu không tồn tại"}}
    gateway = FakeGateway(drafts=[[quote]])
    result = await answer(question="Liên hệ phòng đào tạo?", index=UnitIndex([source]), gateway=gateway,
                          facts=(replace(fact, **changes[change]),))
    assert result.kind == "answer" and gateway.generated == 1


@pytest.mark.asyncio
async def test_fact_still_runs_deterministic_verification():
    source = unit("Không được bỏ hồ sơ.\nPhòng đào tạo nhận hồ sơ.")
    fact = Fact("f", "contact", "phòng đào tạo", "hồ sơ", source.unit_id, "Phòng đào tạo nhận hồ sơ.")
    gateway = FakeGateway()
    result = await answer(question="Liên hệ phòng đào tạo?", index=UnitIndex([source]), gateway=gateway, facts=(fact,))
    # The unit carries a condition ("Không được ..."), so the fact line is not a self-contained answer:
    # the fast path is skipped and the normal generation + verification path runs instead.
    assert any(r.request_id == "rag_v2_generation" for r in gateway.requests)


@pytest.mark.asyncio
async def test_context_is_not_exposed_as_a_citation_quote():
    from campus247.rag_v2.ingest.units import CONTEXT_START, SOURCE_SEPARATOR
    source = unit(CONTEXT_START + "Quy chế" + SOURCE_SEPARATOR + TEXT)
    result = await answer(index=UnitIndex([source]))
    assert result.kind == "answer" and result.citations[0].quote == TEXT


@pytest.mark.asyncio
async def test_elliptical_user_history_reaches_understanding():
    gateway = FakeGateway()
    result = await RagV2Service().answer("Còn K65?", ("Học phí đại trà K64 bao nhiêu?",),
        gateway=gateway, index=UnitIndex(), reranker=Reranker(), embed=None)
    assert result.kind in {"answer", "clarify"}
    if gateway.requests:
        assert "học phí" in gateway.requests[0].input_items[0]["content"]


@pytest.mark.asyncio
async def test_multiple_facts_in_one_unit_keep_both_original_values_in_citation():
    first = "Phòng đào tạo: điện thoại 02438691300."
    second = "Phòng đào tạo: daotao@huce.edu.vn."
    source = unit(first + "\n" + second)
    facts = (Fact("one", "contact", "phòng đào tạo", "02438691300", source.unit_id, first),
             Fact("two", "contact", "phòng đào tạo", "daotao@huce.edu.vn", source.unit_id, second))
    result = await answer(question="Liên hệ phòng đào tạo?", index=UnitIndex([source]), facts=facts)
    assert result.kind == "answer" and len(result.statements) == 2
    assert result.citations[0].quote == source.text


@pytest.mark.asyncio
async def test_semantic_request_respects_retained_gateway_output_cap():
    class Bounded(FakeGateway):
        async def generate(self, request):
            assert request.deadline_ms <= 5000 and request.max_output_tokens <= 1000
            return await super().generate(request)
    gateway = Bounded(drafts=[[TEXT] * 32])
    result = await answer(gateway=gateway)
    assert result.kind == "answer" and gateway.requests[-1].max_output_tokens == 1000


@pytest.mark.asyncio
async def test_one_failed_semantic_verdict_is_retried_before_giving_up():
    class FlakyOnce(FakeGateway):
        failed = False

        async def generate(self, request):
            if request.request_id == "rag_v2_semantic" and not self.failed:
                self.failed = True
                return LlmResponse(LlmResponseStatus.FAILED, "fake", "fake")
            return await super().generate(request)

    gateway = FlakyOnce()
    result = await answer(gateway=gateway)
    assert result.kind == "answer" and gateway.failed


@pytest.mark.asyncio
async def test_fact_line_with_a_condition_in_its_unit_is_not_answered_from_the_fact_alone():
    from dataclasses import replace as _replace

    from campus247.rag_v2.facts.extract import extract_facts
    text = "Học phí đại trà: 580.500 đồng/tín chỉ.\nMức trên chỉ áp dụng cho học phần học lại."
    u = _replace(unit(text), doc_title="Học phí đại trà K64")
    facts = tuple(extract_facts([u]))
    gateway = FakeGateway(drafts=[[text]])
    result = await RagV2Service(facts).answer("Học phí đại trà K64 bao nhiêu?", (), gateway=gateway,
        index=UnitIndex([u]), reranker=Reranker(), embed=None)
    # No answer from the fact fast path: the model path (and its semantic check) must run.
    assert any(r.request_id == "rag_v2_generation" for r in gateway.requests) or result.kind != "answer"


@pytest.mark.asyncio
async def test_condition_in_the_neighbouring_row_blocks_the_fact_fast_path():
    from dataclasses import replace as _replace

    from campus247.rag_v2.facts.extract import extract_facts
    row = "1. Học phí đại trà K64: 580.500 đồng/tín chỉ.\n2. Mức trên chỉ áp dụng cho học phần học lại."
    first = _replace(unit("1. Học phí đại trà K64: 580.500 đồng/tín chỉ."), doc_title="Học phí đại trà K64")
    parent = _replace(first, unit_id="parent", text=row)

    class WithParent(UnitIndex):
        def chunk_unit(self, chunk_id):
            return parent

    gateway = FakeGateway(drafts=[[row]])
    await RagV2Service(tuple(extract_facts([first]))).answer("Học phí đại trà K64 bao nhiêu?", (), gateway=gateway,
        index=WithParent([first]), reranker=Reranker(), embed=None)
    assert any(r.request_id == "rag_v2_generation" for r in gateway.requests)


@pytest.mark.asyncio
async def test_comma_separated_compound_question_leaves_the_fact_fast_path():
    from dataclasses import replace as _replace

    from campus247.rag_v2.facts.extract import extract_facts
    text = "Học phí đại trà: 580.500 đồng/tín chỉ."
    u = _replace(unit(text), doc_title="Học phí đại trà K64")
    gateway = FakeGateway(drafts=[[text]])
    await RagV2Service(tuple(extract_facts([u]))).answer("Học phí đại trà K64 bao nhiêu, đóng như thế nào?", (), gateway=gateway,
        index=UnitIndex([u]), reranker=Reranker(), embed=None)
    assert any(r.request_id == "rag_v2_generation" for r in gateway.requests)


@pytest.mark.asyncio
async def test_one_slow_generation_call_is_retried_within_the_budget():
    class SlowOnce(FakeGateway):
        slow = True

        async def generate(self, request):
            if request.request_id == "rag_v2_generation" and self.slow:
                self.slow = False
                raise TimeoutError
            return await super().generate(request)

    gateway = SlowOnce()
    result = await answer(gateway=gateway)
    assert result.kind == "answer" and [r.request_id for r in gateway.requests].count("rag_v2_generation") == 1


@pytest.mark.asyncio
async def test_two_slow_generation_calls_are_a_typed_transient_error():
    class AlwaysSlow(FakeGateway):
        async def generate(self, request):
            if request.request_id == "rag_v2_generation":
                raise TimeoutError
            return await super().generate(request)

    assert (await answer(gateway=AlwaysSlow())).kind == "transient_error"


class Deciding(FakeGateway):
    def __init__(self, decision, question="", **kwargs):
        super().__init__(**kwargs)
        self.decision, self.question = decision, question

    async def generate(self, request):
        if request.request_id == "rag_v2_generation":
            self.requests.append(request)
            value = {"decision": self.decision, "clarify_question": self.question, "statements": []}
            return LlmResponse(LlmResponseStatus.COMPLETED, "fake", "fake", structured_output=value,
                               output_text=json.dumps(value))
        return await super().generate(request)


@pytest.mark.asyncio
@pytest.mark.parametrize(("decision", "kind", "reason"), [
    ("clarify", "clarify", None), ("no_source", "refuse", "no_source"), ("out_of_scope", "refuse", "out_of_scope")])
async def test_model_decision_not_to_answer_becomes_a_typed_outcome_without_verification_calls(decision, kind, reason):
    gateway = Deciding(decision, "Bạn hỏi đợt nào?")
    result = await answer(gateway=gateway)
    assert result.kind == kind and result.reason == reason and not result.statements and not result.citations
    assert [r.request_id for r in gateway.requests] == ["rag_v2_generation"]
    if kind == "clarify":
        assert "Bạn hỏi đợt nào?" in result.text


@pytest.mark.asyncio
async def test_clarify_question_with_a_link_or_address_is_replaced_by_a_fixed_question():
    result = await answer(gateway=Deciding("clarify", "Gửi mail tới a@b.vn hoặc xem http://x.vn"))
    assert result.kind == "clarify" and "a@b.vn" not in result.text and "http" not in result.text


@pytest.mark.asyncio
async def test_unknown_or_missing_decision_is_treated_as_answer_and_verified_as_before():
    assert (await answer(gateway=Deciding("whatever"))).kind == "refuse"      # empty statements, nothing verified
    assert (await answer(gateway=FakeGateway())).kind == "answer"            # legacy output without a decision
