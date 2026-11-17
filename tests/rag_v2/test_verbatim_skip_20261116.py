"""Lever L1: the model-based support check is skipped only for exact excerpts, never otherwise."""
import logging

import pytest
from campus247.rag_v2.types import Statement, Scope
from campus247.rag_v2.verification.verbatim import all_verbatim, is_verbatim, mode

from tests.rag_v2.test_service import FakeGateway, TEXT, UnitIndex, answer, unit

QUERY = "dieu kien bao luu la gi"


def units(text=TEXT):
    u = unit(text)
    return {"U1": u}


def test_exact_excerpt_is_verbatim_and_a_paraphrase_or_splice_is_not():
    assert is_verbatim(Statement(TEXT, ("U1",)), units(), QUERY)
    assert is_verbatim(Statement("- " + TEXT.rstrip(".") + ";", ("U1",)), units(), QUERY)       # bullets/punctuation only
    assert not is_verbatim(Statement("Hồ sơ bảo lưu nộp ở phòng đào tạo.", ("U1",)), units(), QUERY)
    assert not is_verbatim(Statement(TEXT + " Sinh viên được bảo lưu tối đa 2 năm.", ("U1",)), units(), QUERY)
    assert not is_verbatim(Statement(TEXT, ("missing",)), units(), QUERY)


def test_short_text_and_unrelated_excerpt_are_not_verbatim():
    assert not is_verbatim(Statement("Phòng đào tạo.", ("U1",)), units("Phòng đào tạo."), QUERY)
    other = "Học phí được nộp tại phòng kế hoạch tài chính của trường."
    assert not is_verbatim(Statement(other, ("U1",)), units(other), QUERY)     # exact, but not about the question


def test_one_non_excerpt_statement_makes_the_answer_ineligible():
    both = [Statement(TEXT, ("U1",)), Statement("Điều này áp dụng cho mọi khóa.", ("U1",))]
    assert not all_verbatim(both, units(), QUERY)
    assert not all_verbatim([], units(), QUERY)


def test_mode_defaults_to_off(monkeypatch):
    monkeypatch.delenv("CAMPUS247_RAG_SKIP_VERBATIM_SEMANTIC", raising=False)
    assert mode() == "off"
    monkeypatch.setenv("CAMPUS247_RAG_SKIP_VERBATIM_SEMANTIC", "banana")
    assert mode() == "off"


@pytest.mark.asyncio
async def test_off_keeps_the_semantic_call(monkeypatch):
    monkeypatch.setenv("CAMPUS247_RAG_SKIP_VERBATIM_SEMANTIC", "off")
    gateway = FakeGateway()
    result = await answer(gateway=gateway)
    assert result.kind == "answer"
    assert [r.request_id for r in gateway.requests] == ["rag_v2_generation", "rag_v2_semantic"]


@pytest.mark.asyncio
async def test_on_skips_the_semantic_call_for_an_exact_excerpt(monkeypatch):
    monkeypatch.setenv("CAMPUS247_RAG_SKIP_VERBATIM_SEMANTIC", "on")
    gateway = FakeGateway()
    result = await answer(gateway=gateway)
    assert result.kind == "answer" and result.text == TEXT and result.citations
    assert [r.request_id for r in gateway.requests] == ["rag_v2_generation"]


@pytest.mark.asyncio
async def test_on_still_asks_the_model_for_a_paraphrase(monkeypatch):
    monkeypatch.setenv("CAMPUS247_RAG_SKIP_VERBATIM_SEMANTIC", "on")
    gateway = FakeGateway(drafts=[["Hồ sơ bảo lưu được nộp ở phòng đào tạo."]], supported=False)
    result = await answer(gateway=gateway)
    assert [r.request_id for r in gateway.requests] == ["rag_v2_generation", "rag_v2_semantic"]
    assert result.kind != "answer"           # the model said unsupported, so nothing is presented as supported


@pytest.mark.asyncio
async def test_on_never_skips_when_the_scope_was_relaxed(monkeypatch):
    monkeypatch.setenv("CAMPUS247_RAG_SKIP_VERBATIM_SEMANTIC", "on")
    gateway = FakeGateway()
    index = UnitIndex([unit(scope=Scope(academic_years=("2021-2022",)))])
    await answer(question="Điều kiện bảo lưu năm học 2025-2026 là gì?", gateway=gateway, index=index)
    assert "rag_v2_semantic" in [r.request_id for r in gateway.requests]


@pytest.mark.asyncio
async def test_shadow_asks_the_model_and_records_agreement(monkeypatch, caplog):
    monkeypatch.setenv("CAMPUS247_RAG_SKIP_VERBATIM_SEMANTIC", "shadow")
    caplog.set_level(logging.WARNING, logger="campus247.rag_v2")
    gateway = FakeGateway(supported=False)
    await answer(gateway=gateway)
    assert [r.request_id for r in gateway.requests] == ["rag_v2_generation", "rag_v2_semantic"]
    assert "rag_v2_l1_shadow eligible=1 statements=1 model_all_supported=0" in caplog.text
