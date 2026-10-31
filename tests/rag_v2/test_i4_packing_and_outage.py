"""Context packing is bounded by real bytes and honest; outages are not reported as missing sources."""
import json

import pytest
from campus247.ports.llm import LlmResponse, LlmResponseStatus
from campus247.rag_v2.generation.packing import MAX_SOURCES, payload_bytes, pack_context
from campus247.rag_v2.types import Scope, Unit

from tests.rag_v2.test_service import TEXT, FakeGateway, UnitIndex, answer, unit


def make(uid, text, chunk="c"):
    return Unit(uid, (chunk,), "doc", "v", "Quy chế", "quy_che", "clause", "Điều 1", 1, text, scope=Scope())


def test_parent_is_preferred_and_shared_by_sibling_units():
    parent = make("parent", "x" * 500, "c1")
    packed, truncated = pack_context([make("a", "1", "c1"), make("b", "2", "c1")],
                                     lambda chunk: parent, budget=10_000)
    assert list(packed) == ["parent"] and not truncated


def test_oversized_parent_falls_back_to_the_fine_unit_and_flags_it():
    fine = make("fine", "Mức thu 580.500 đồng.", "c1")
    giant = make("giant", "y" * 60_000, "c1")
    packed, truncated = pack_context([fine], lambda chunk: giant, budget=19_000)
    assert list(packed) == ["fine"] and truncated


def test_budget_is_never_exceeded_without_any_parent():
    units = [make(f"u{i}", "z" * 3_000, f"c{i}") for i in range(12)]
    packed, truncated = pack_context(units, None, budget=19_000)
    assert sum(payload_bytes(unit) for unit in packed.values()) <= 19_000
    assert len(packed) <= MAX_SOURCES and truncated


def test_source_count_is_bounded_for_the_semantic_verifier():
    units = [make(f"u{i}", "ngắn", f"c{i}") for i in range(12)]
    packed, truncated = pack_context(units, None, budget=19_000)
    assert len(packed) == MAX_SOURCES and truncated


class WithParent(UnitIndex):
    def __init__(self, parent_text):
        super().__init__()
        self.parent_text = parent_text

    def chunk_unit(self, chunk_id):
        return make("p" * 16, self.parent_text, chunk_id)


@pytest.mark.asyncio
async def test_answer_from_a_fine_unit_is_partial_when_the_parent_could_not_be_sent():
    result = await answer(index=WithParent("w" * 60_000))
    assert result.kind == "partial" and result.partial_note and result.statements[0].text == TEXT


@pytest.mark.asyncio
async def test_complete_parent_keeps_a_full_answer():
    result = await answer(index=WithParent(TEXT + " Thêm quy định khác."))
    assert result.kind == "answer"


class Down(UnitIndex):
    def lexical(self, query, limit, *, allowed=None):
        return []

    async def vector(self, query, limit, *, allowed=None):
        raise ConnectionError("embedding service down")


@pytest.mark.asyncio
async def test_vector_outage_with_no_lexical_hit_is_a_transient_error_not_no_source():
    gateway = FakeGateway()
    result = await answer(index=Down(), gateway=gateway)
    assert result.kind == "transient_error" and result.reason is None
    assert not gateway.requests


class Garbage(FakeGateway):
    async def generate(self, request):
        if request.request_id == "rag_v2_generation":
            self.requests.append(request)
            value = {"unexpected": 1}
            return LlmResponse(LlmResponseStatus.COMPLETED, "fake", "fake", structured_output=value,
                               output_text=json.dumps(value))
        return await super().generate(request)


@pytest.mark.asyncio
async def test_unparseable_generation_is_a_transient_error_not_unverified():
    result = await answer(gateway=Garbage())
    assert result.kind == "transient_error"
