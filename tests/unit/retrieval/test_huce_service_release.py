"""Real retained service provenance and complete source readback, without model calls."""
import hashlib
from datetime import datetime, UTC
from pathlib import Path

import pytest

from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.asyncio
async def test_office_excerpt_keeps_preconditions_steps_and_original_provenance():
    store = PublicKnowledgeStore(ROOT / "data/huce-public-20261013", tenant_id="HUCE", campus_id="HUCE")
    context = RetrievalContext(AuthorizedScope("HUCE", "HUCE", "actor", frozenset({"STUDENT"}),
        frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})),
        "vi", datetime.now(UTC), SimulationPolicy.DENY, "1" * 32)
    rows = await store.search("cai Office 365 bang tai khoan truong", context)
    row = rows[0]
    assert "ttcntt.huce.edu.vn/huong-dan-tai-office-365" in row["canonical_uri"]
    read = await store.read(row["source_id"], row["document_version_id"], row["chunk_id"], context=context)
    assert read.content_text == row["content_text"]
    assert read.content_sha256 == hashlib.sha256(read.content_text.encode()).hexdigest()
    assert all(f"Bước {n}:" in read.content_text for n in range(1, 5))
    assert "được cung cấp" in read.content_text and "Install apps" in read.content_text
    provenance = row["provenance"]
    assert provenance["published_at"] == "2025-02-10" and provenance["legal_effective_from"] is None
    assert provenance["applicability"]["cohort"] is None
    assert provenance["limitations"] and provenance["ocr_quality"] == "not_applicable_native_html"
    original = ROOT / "data" / provenance["source_file"]
    assert hashlib.sha256(original.read_bytes()).hexdigest() == provenance["source_sha256"]
    assert (ROOT / provenance["visual_evidence"]).is_file()
    assert row["locator"] == {"section_path": row["section_path"]}


@pytest.mark.asyncio
async def test_qlda_visual_correction_preserves_original_document_and_old_citation():
    directory = ROOT / "data/huce-public-20261013"
    # The later reviewed-corrections release also re-segments the K71 curricula, so the automated
    # pre-correction row exists only when both later releases are excluded.
    old = PublicKnowledgeStore(directory, tenant_id="HUCE", campus_id="HUCE",
                               include_reviewed_course_review=False, include_reviewed_corrections=False)
    new = PublicKnowledgeStore(directory, tenant_id="HUCE", campus_id="HUCE")
    prior = next(row for row in old.rows if row["title"] == "K71 — Quản lý dự án")
    corrected = next(row for row in new.rows if row["title"] == "K71 — Quản lý dự án")
    assert corrected["chunk_id"] != prior["chunk_id"]
    assert corrected["document_version_id"] == prior["document_version_id"]
    assert corrected["source_id"] == prior["source_id"]
    assert prior["chunk_id"] not in {row["chunk_id"] for row in new.rows}
    assert "NGÀNH QUẢN LÝ DỰ ÁN (K71QLDA)" in corrected["content_text"]
    assert "Học kỳ 1\n420103 – 3\nTriết học Mác - Lênin" in corrected["content_text"]
    assert "Tổng: 131TC (Không tính HP giáo dục thể chất" in corrected["content_text"]
    context = RetrievalContext(AuthorizedScope("HUCE", "HUCE", "actor", frozenset({"STUDENT"}),
        frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})),
        "vi", datetime.now(UTC), SimulationPolicy.DENY, "1" * 32)
    historical = await new.read(prior["source_id"], prior["document_version_id"], prior["chunk_id"], context=context)
    assert historical.content_text == prior["content_text"]
    assert historical.content_sha256 == prior["quote_span_hash"]


@pytest.mark.asyncio
async def test_withdrawal_chart_keeps_student_step_and_separate_wishlist_flow():
    directory = ROOT / "data/huce-public-20261013"
    old = PublicKnowledgeStore(directory, tenant_id="HUCE", campus_id="HUCE", include_reviewed_withdrawal=False)
    new = PublicKnowledgeStore(directory, tenant_id="HUCE", campus_id="HUCE")
    prior = next(row for row in old.rows if row["section_path"] == "Trang 27")
    corrected = next(row for row in new.rows if row["version_label"] == "reviewed-withdrawal-20261021")
    assert prior["chunk_id"] not in {row["chunk_id"] for row in new.rows}
    upper, lower = corrected["content_text"].split("QUY TRÌNH MỞ LỚP MÔN HỌC NGUYỆN VỌNG")
    assert "Bước 2: Sinh viên gửi yêu cầu rút bớt học phần trên hệ thống quản lý đào tạo của Trường." in upper
    assert "Phòng Quản lý Sinh viên" not in upper
    assert upper.count("Bước ") == 4 and lower.count("Bước ") == 6
    assert "thông báo điều kiện và thời gian" in upper
    assert not any(word in upper for word in ("hoàn phí", "hoàn tiền", "miễn phí"))
    context = RetrievalContext(AuthorizedScope("HUCE", "HUCE", "actor", frozenset({"STUDENT"}),
        frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})),
        "vi", datetime.now(UTC), SimulationPolicy.DENY, "1" * 32)
    historical = await new.read(prior["source_id"], prior["document_version_id"], prior["chunk_id"], context=context)
    assert historical.content_text == prior["content_text"]
    assert historical.content_sha256 == prior["quote_span_hash"]
