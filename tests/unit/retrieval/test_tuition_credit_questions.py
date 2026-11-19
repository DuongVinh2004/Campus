"""Colloquial question scope and public source readback, not answer snapshots."""
import hashlib
from datetime import datetime, UTC
from pathlib import Path

import pytest

from campus247.application.conversation.followup import question_topics
from campus247.application.conversation.understanding import conversational_response, retrieval_subqueries
from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy


def context():
    return RetrievalContext(AuthorizedScope("HUCE", "HUCE", "actor", frozenset({"STUDENT"}),
        frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})),
        "vi", datetime.now(UTC), SimulationPolicy.DENY, "1" * 32)


@pytest.mark.parametrize("question,topic", [
    ("học phí đang là bao nhiêu", "hoc phi"),
    ("một tín chỉ bao nhiêu tiền", "hoc phi"),
    ("1 tin gia bao nhieu", "hoc phi"),
    ("học kỹ sư cần bao nhiêu tín", "tin chi tot nghiep"),
    ("ky su can may tin", "tin chi tot nghiep"),
])
def test_colloquial_questions_keep_original_qualifiers(question, topic):
    assert topic in question_topics(question)
    assert conversational_response(question) is None
    assert retrieval_subqueries(question)[0].startswith(question)


@pytest.mark.parametrize("question", [
    "một tín chỉ có bao nhiêu giờ tự học", "học kỳ này đăng ký bao nhiêu tín chỉ",
    "kỹ sư có thể xin bảng điểm ở đâu", "học phí kỹ sư một tín chỉ bao nhiêu tiền",
])
def test_program_credit_topic_does_not_capture_other_credit_requests(question):
    assert "tin chi tot nghiep" not in question_topics(question)


@pytest.mark.asyncio
async def test_supplemental_sources_are_original_scoped_and_hash_bound():
    root = Path(__file__).resolve().parents[3]
    store = PublicKnowledgeStore(root / "data/huce-public-20261013", tenant_id="HUCE", campus_id="HUCE")
    rows = [row for row in store.rows if row["version_label"] == "public-20261020"]
    assert len(rows) == 3
    fees = next(row for row in rows if row["page_start"] == 2)
    assert "K65 đến K68 | 592.500" in fees["content_text"]
    assert "Từ K69 | 547.000" in fees["content_text"]
    assert "K66 trở về trước (ĐVHT) | 336.000" in fees["content_text"]
    program = next(row for row in rows if "fit.huce.edu.vn" in row["canonical_uri"])
    assert "kỹ sư CNTT" in program["content_text"] and "180 tín chỉ trong 5 năm học" in program["content_text"]
    for row in rows:
        source = await store.read(row["source_id"], row["document_version_id"], row["chunk_id"], context=context())
        assert source.content_sha256 == hashlib.sha256(source.content_text.encode()).hexdigest()
        assert source.content_text == row["content_text"]
