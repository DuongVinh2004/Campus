"""Offline regressions: fake gateways; exact synthetic source spans checked by code."""
from dataclasses import replace
from hashlib import sha256

import pytest

from campus247.agent.nodes.compose import OutputGuardNode
from campus247.agent.nodes.rag_v2 import GUARD_BLOCKED_MESSAGE
from campus247.agent.state import Terminal
from campus247.domain.publication import VerifiedPublication
from campus247.rag_v2.discipline import verified_general_discipline_rule
from campus247.rag_v2.types import Citation, Outcome, Statement
from tests.rag_v2.test_graph_integration import context, setup as build_stack
from tests.rag_v2.test_service import FakeGateway


RULE = "Sinh viên nào vi phạm nội quy thì bị kỷ luật ở mức đình chỉ học tập."
SCHOLARSHIP = "Sinh viên không bị kỷ luật từ mức khiển trách trở lên."


def evidence(text=RULE):
    row = {"source_id": "doc", "document_version_id": "version", "chunk_id": "chunk",
           "canonical_uri": "https://huce.edu.vn/quy-che", "content_text": text,
           "evidence_sha256": sha256(text.encode()).hexdigest(), "simulation_label": False,
           "release_id": "release"}
    citation = Citation("unit", ("chunk",), "doc", "version", "Quy chế", "Điều 1", 1, text)
    return Outcome("answer", text, (Statement(text, ("unit",)),), (citation,)), {"chunk": row}


def attested(row):
    row["canonical_uri"] = "https://attachments.example.test/rule.pdf"
    row["_verified_publication"] = VerifiedPublication(
        "https://daotao.huce.edu.vn/quy-che", row["canonical_uri"], row["source_id"],
        row["document_version_id"], row["evidence_sha256"], "a" * 64, row["release_id"])


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [RULE, SCHOLARSHIP,
    "Hạng tốt nghiệp bị giảm một mức khi sinh viên đã bị kỷ luật.",
    "Sinh viên đã bị kỷ luật khi vi phạm nội quy thì không đủ điều kiện xét học bổng."])
@pytest.mark.parametrize("kind", ["answer", "partial"])
async def test_official_verbatim_generic_rule_reaches_final_answer(text, kind):
    drafts = [[text]] if kind == "answer" else [[text, "Nộp 999 hồ sơ."]]
    stack = build_stack(source=text, gateway=FakeGateway(drafts=drafts))
    state = await stack.workflow.arun(stack.turn, retrieval_context=context())
    assert state.terminal == Terminal.ANSWERED
    assert text in state.draft.text and state.draft.grounded_claims
    assert "RAG_V2_" + kind.upper() in state.errors
    assert all(text in c["quote"] for c in state.tool_flow.candidates)


@pytest.mark.asyncio
async def test_only_discipline_rejection_is_overridden_through_the_whole_graph(monkeypatch):
    # Exercise the fallback even when the legacy guard cannot verify v2 evidence.
    execute = OutputGuardNode.execute

    def legacy_guard(self, state):
        if "kỷ luật" in state.draft.text:
            return execute(self, replace(state, draft=replace(state.draft, grounded_claims=())))
        return execute(self, state)

    monkeypatch.setattr(OutputGuardNode, "execute", legacy_guard)
    stack = build_stack(source=RULE, gateway=FakeGateway(drafts=[[RULE]]))
    state = await stack.workflow.arun(stack.turn, retrieval_context=context())
    assert state.terminal == Terminal.ANSWERED and RULE in state.draft.text
    assert "RAG_V2_DISCIPLINE_RULE_VERIFIED" in state.errors
    assert "[verified rule]" not in state.draft.text


@pytest.mark.asyncio
async def test_another_guard_rejection_cannot_be_overridden(monkeypatch):
    execute = OutputGuardNode.execute

    def other_guard(self, state):
        if "kỷ luật" in state.draft.text:
            return replace(state, terminal=Terminal.SAFE_FAILURE,
                           errors=state.errors + ("Policy violation: another safety rule",))
        return execute(self, state)

    monkeypatch.setattr(OutputGuardNode, "execute", other_guard)
    stack = build_stack(source=RULE, gateway=FakeGateway(drafts=[[RULE]]))
    state = await stack.workflow.arun(stack.turn, retrieval_context=context())
    assert state.terminal == Terminal.ABSTAINED and state.draft.text == GUARD_BLOCKED_MESSAGE
    assert "RAG_V2_DISCIPLINE_RULE_VERIFIED" not in state.errors


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [
    "Bạn đã bị kỷ luật và không được học bổng.",
    "Em đã bị kỷ luật.",
    "Sinh viên Nguyễn Văn An đã bị kỷ luật.",
    "Sinh viên SV240000 không bị kỷ luật.",
    "Sinh viên này không bị kỷ luật.",
    "Sinh viên đó không bị kỷ luật.",
    "Sinh viên tên An không bị kỷ luật.",
    "Sinh viên đã bị kỷ luật từ mức cảnh cáo trở lên.",
    "Sinh viên phải bị kỷ luật.",
    "Sinh viên đã bị xử lý kỷ luật.",
    "Sinh viên có hồ sơ đã bị kỷ luật từ mức cảnh cáo trở lên.",
    "Điều kiện xét học bổng: sinh viên đã chịu kỷ luật.",
    RULE + " Bạn đã bị kỷ luật.",
    RULE + " Sinh viên đã bị kỷ luật.",
    "Sinh viên đã bị kỷ luật. Khi xét học bổng cần xem quy chế.",
])
async def test_personal_or_unconditional_verdict_is_blocked_even_if_exactly_sourced(text):
    stack = build_stack(source=text, gateway=FakeGateway(drafts=[[text]]))
    state = await stack.workflow.arun(stack.turn, retrieval_context=context())
    assert state.terminal == Terminal.ABSTAINED and state.draft.text == GUARD_BLOCKED_MESSAGE
    assert "RAG_V2_REFUSE_UNSAFE" in state.errors and not state.draft.grounded_claims


@pytest.mark.asyncio
@pytest.mark.parametrize("extra", ["vi phạm pháp luật", "chẩn đoán", "kết luận pháp lý",
    "sudo", "password=privatevalue", "secret_token=privatevalue",
    "sk-abcdefghijklmnop1234", "bearer abcdefghijklmnop123456",
    "hứa sẽ trả lời trong vòng 2 giờ", "đã gọi thành công"])
async def test_every_other_shared_rejection_survives_the_discipline_exception(extra):
    text = SCHOLARSHIP + " " + extra + "."
    stack = build_stack(source=text, gateway=FakeGateway(drafts=[[text]]))
    state = await stack.workflow.arun(stack.turn, retrieval_context=context())
    assert state.terminal == Terminal.ABSTAINED and state.draft.text == GUARD_BLOCKED_MESSAGE
    assert "RAG_V2_REFUSE_UNSAFE" in state.errors


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["unofficial", "simulation", "not_verbatim"])
async def test_unofficial_simulated_or_paraphrased_rule_is_blocked(fault):
    text = SCHOLARSHIP
    source = text if fault != "not_verbatim" else "Sinh viên không bị kỷ luật ở mức cảnh cáo trở lên."
    stack = build_stack(source=source, gateway=FakeGateway(drafts=[[text]]))
    if fault == "unofficial":
        stack.row["canonical_uri"] = "https://example.test/quy-che"
    elif fault == "simulation":
        stack.row["simulation_label"] = True
    state = await stack.workflow.arun(stack.turn, retrieval_context=context())
    assert state.terminal == Terminal.ABSTAINED and state.draft.text == GUARD_BLOCKED_MESSAGE


@pytest.mark.asyncio
async def test_attested_published_attachment_uses_the_same_source_binding():
    stack = build_stack(source=RULE, gateway=FakeGateway(drafts=[[RULE]]))
    attested(stack.row)
    state = await stack.workflow.arun(stack.turn, retrieval_context=context())
    assert state.terminal == Terminal.ANSWERED and RULE in state.draft.text


@pytest.mark.asyncio
async def test_semantically_rejected_statement_cannot_receive_the_exception():
    stack = build_stack(source=RULE, gateway=FakeGateway(drafts=[[RULE]], supported=False))
    state = await stack.workflow.arun(stack.turn, retrieval_context=context())
    assert state.terminal == Terminal.ABSTAINED and not state.draft.grounded_claims
    assert RULE not in state.draft.text


@pytest.mark.parametrize("fault", ["missing_ref", "missing_citation", "duplicate_citation",
    "missing_row", "wrong_source", "wrong_version", "wrong_chunk", "wrong_hash",
    "empty_chunks", "empty_quote", "quote_not_in_row", "unaccepted_statement"])
def test_missing_or_misbound_v2_evidence_fails_closed(fault):
    outcome, rows = evidence()
    row, citation, statement = rows["chunk"], outcome.citations[0], outcome.statements[0]
    if fault == "missing_ref":
        outcome = replace(outcome, statements=(replace(statement, unit_ids=()),))
    elif fault == "missing_citation":
        outcome = replace(outcome, citations=())
    elif fault == "duplicate_citation":
        outcome = replace(outcome, citations=(citation, citation))
    elif fault == "missing_row":
        rows = {}
    elif fault in {"wrong_source", "wrong_version", "wrong_chunk", "wrong_hash"}:
        key = {"wrong_source": "source_id", "wrong_version": "document_version_id",
               "wrong_chunk": "chunk_id", "wrong_hash": "evidence_sha256"}[fault]
        row[key] = "wrong"
    elif fault == "empty_chunks":
        outcome = replace(outcome, citations=(replace(citation, chunk_ids=()),))
    elif fault == "empty_quote":
        outcome = replace(outcome, citations=(replace(citation, quote=""),))
    elif fault == "quote_not_in_row":
        outcome = replace(outcome, citations=(replace(citation, quote=RULE + " invented"),))
    else:
        outcome = replace(outcome, statements=())
    assert not verified_general_discipline_rule(outcome, rows)


@pytest.mark.parametrize("fault", ["other_attachment", "other_source", "other_version",
    "other_release", "changed_evidence", "dict_forgery", "simulation", "unofficial_publisher"])
def test_publication_attestation_cannot_be_reused_or_forged(fault):
    outcome, rows = evidence()
    row = rows["chunk"]
    attested(row)
    assert verified_general_discipline_rule(outcome, rows)
    if fault in {"other_attachment", "other_source", "other_version", "other_release"}:
        key = {"other_attachment": "canonical_uri", "other_source": "source_id",
               "other_version": "document_version_id", "other_release": "release_id"}[fault]
        row[key] += "wrong"
    elif fault == "changed_evidence":
        row["content_text"] += "\nNew text."
        row["evidence_sha256"] = sha256(row["content_text"].encode()).hexdigest()
    elif fault == "dict_forgery":
        row["_verified_publication"] = row["_verified_publication"].__dict__
    elif fault == "simulation":
        row["simulation_label"] = True
    else:
        row["_verified_publication"] = replace(row["_verified_publication"], publisher_uri="https://example.test")
    assert not verified_general_discipline_rule(outcome, rows)


@pytest.mark.parametrize("statement, source", [
    ("Sinh viên vi phạm quy chế thi bị kỷ luật theo mức đình chỉ học tập.",
     "Điều 12. Sinh viên vi phạm quy chế thi bị kỷ luật theo các mức: khiển trách, đình chỉ học tập."),
    ("Sinh viên thi hộ bị kỷ luật ở mức đình chỉ học tập.",
     "Sinh viên thi hộ hoặc nhờ người thi hộ bị kỷ lu ật ở mức đình chỉ học tập một năm."),
    ("Sinh viên bị khiển trách nếu vi phạm nội quy; mức kỷ luật nặng hơn áp dụng khi tái phạm.",
     "Nội quy: vi phạm lần đầu bị khiể n trách; mức kỷ luậ t nặng hơn áp dụng khi tái phạm."),
])
def test_paraphrase_of_a_general_rule_whose_words_are_in_the_source_is_allowed(statement, source):
    outcome, rows = evidence(source)
    outcome = replace(outcome, statements=(Statement(statement, ("unit",)),))
    assert verified_general_discipline_rule(outcome, rows)


@pytest.mark.parametrize("statement", [
    "Sinh viên thi hộ bị kỷ luật ở mức buộc thôi học.",
    "Sinh viên thi hộ bị kỷ luật ở mức đình chỉ học tập 3 năm.",
])
def test_a_word_or_number_missing_from_the_source_blocks_the_exception(statement):
    outcome, rows = evidence("Sinh viên thi hộ bị kỷ luật ở mức đình chỉ học tập 1 năm.")
    outcome = replace(outcome, statements=(Statement(statement, ("unit",)),))
    assert not verified_general_discipline_rule(outcome, rows)


def test_every_affected_statement_and_every_cited_source_must_qualify():
    outcome, rows = evidence()
    assert verified_general_discipline_rule(outcome, rows)
    personal = Statement("Bạn đã bị kỷ luật.", ("unit",))
    assert not verified_general_discipline_rule(replace(outcome, statements=(*outcome.statements, personal)), rows)
    second = replace(outcome.citations[0], unit_id="other", chunk_ids=("other",))
    rows["other"] = {**rows["chunk"], "chunk_id": "other", "canonical_uri": "https://example.test"}
    mixed = replace(outcome, statements=(Statement(RULE, ("unit", "other")),),
                    citations=(*outcome.citations, second))
    assert not verified_general_discipline_rule(mixed, rows)
