"""Real-source retrieval scope, Vietnamese queries and original citation readback."""
from datetime import datetime, timezone
import hashlib
import json

import pytest

from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore


def context(tenant="HUCE"):
    return RetrievalContext(AuthorizedScope(tenant, "HUCE", "actor", frozenset({"STUDENT"}),
        frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})),
        "vi", datetime.now(timezone.utc), SimulationPolicy.DENY, "1" * 32)


@pytest.fixture
def store(tmp_path):
    manifest = {"public_only": True, "acquired_at": "2026-10-13T01:00:00+07:00", "chunks": [
        {"url": "https://thuvien.huce.edu.vn/huong-dan", "title": "Hướng dẫn thư viện",
            "page": 1, "section": "Phòng tự học", "text": "Trao đổi, học nhóm, tự học: Tầng 2 - Phòng học nhóm."},
        {"url": "https://huce.edu.vn/so-tay", "title": "Sổ tay sinh viên", "page": 2,
            "section": "Một cửa", "text": "Sinh viên xin bảng điểm qua hệ thống hành chính một cửa."},
    ]}
    (tmp_path / "corpus.json").write_text(json.dumps(manifest), encoding="utf-8")
    return PublicKnowledgeStore(tmp_path, tenant_id="HUCE", campus_id="HUCE")


@pytest.mark.asyncio
async def test_unaccented_query_retrieves_actual_source_and_source_read_is_bound(store):
    values = await store.search("phong tu hoc thu vien o dau", context())
    assert values[0]["section_path"] == "Phòng tự học"
    assert values[0]["source_status"] == "CURRENT" and not values[0]["simulation_label"]
    row = values[0]
    source = await store.read(row["source_id"], row["document_version_id"], row["chunk_id"], context=context())
    assert source.content_sha256 == hashlib.sha256(source.content_text.encode()).hexdigest()
    assert await store.read(row["source_id"], row["document_version_id"], "wrong-chunk", context=context()) is None


@pytest.mark.asyncio
async def test_scope_mismatch_does_not_read_public_index(store):
    with pytest.raises(ValueError):
        await store.search("bảng điểm", context("OTHER"))
