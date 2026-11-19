from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[3]
API_SRC = ROOT / "services" / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from campus247.infrastructure.retrieval.lexical import LexicalSearchAdapter, RetrievalCandidate

MIGRATION_0001 = ROOT / "services" / "api" / "migrations" / "versions" / "0001_identity.py"
MIGRATION_0002 = ROOT / "services" / "api" / "migrations" / "versions" / "0002_knowledge.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def db_conn(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    engine = create_engine("sqlite:///:memory:", echo=False)
    mod1 = load_module("migration_0001", MIGRATION_0001)
    mod2 = load_module("migration_0002", MIGRATION_0002)

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        mod1.op = op
        mod1.upgrade()
        mod2.op = op
        mod2.upgrade()
        conn.commit()

        # Seed knowledge items
        conn.execute(
            text(
                """
                INSERT INTO knowledge_source (id, source_type, canonical_uri, title, owner_unit, authority_level, approval_status, is_synthetic, version)
                VALUES ('018f6c4a-5b6c-7123-8abc-def012345601', 'OFFICIAL_DOCUMENT', 'https://huce.edu.vn/doc/hocphi', 'Quy chế Học phí', 'Phòng Đào tạo', 90, 'APPROVED', 1, 1);
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO document_version (id, knowledge_source_id, version_label, content_checksum, status, storage_object_key, version)
                VALUES ('018f6c4a-5b6c-7123-8abc-def012345602', '018f6c4a-5b6c-7123-8abc-def012345601', 'v1.0', 'sha256:abc', 'PUBLISHED', 'docs/hp.pdf', 1);
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO knowledge_chunk (id, document_version_id, ordinal, section_path, content_text, content_checksum, version)
                VALUES
                ('018f6c4a-5b6c-7123-8abc-def012345603', '018f6c4a-5b6c-7123-8abc-def012345602', 1, 'Dieu 1', 'Mức học phí tiêu chuẩn HUCE là 480.000 đ một tín chỉ', 'sha256:c1', 1),
                ('018f6c4a-5b6c-7123-8abc-def012345604', '018f6c4a-5b6c-7123-8abc-def012345602', 2, 'Dieu 2', 'Thời hạn nộp học phí học kỳ 1 trước 30/10', 'sha256:c2', 1);
                """
            )
        )
        conn.commit()
        yield conn


def test_lexical_search_matches_keyword(db_conn) -> None:
    adapter = LexicalSearchAdapter()
    candidates = adapter.search(db_conn, query="học phí tiêu chuẩn", limit=5)
    assert len(candidates) >= 1
    assert isinstance(candidates[0], RetrievalCandidate)
    assert candidates[0].chunk_id == "018f6c4a-5b6c-7123-8abc-def012345603"
    assert "480.000" in candidates[0].content_text
    assert candidates[0].score > 0.0


def test_lexical_search_empty_query_returns_empty(db_conn) -> None:
    adapter = LexicalSearchAdapter()
    assert adapter.search(db_conn, query="   ") == []


def test_lexical_search_no_match_returns_empty(db_conn) -> None:
    adapter = LexicalSearchAdapter()
    candidates = adapter.search(db_conn, query="xây cầu đường cao tốc không tồn tại")
    assert candidates == []


@pytest.mark.parametrize("environment", ["development", "staging", "production", "testing", ""])
def test_sqlite_helper_is_unavailable_outside_explicit_test_profile(db_conn, monkeypatch, environment):
    from campus247.application.retrieval.filters import RetrievalFilterError
    monkeypatch.setenv("ENVIRONMENT", environment)
    with pytest.raises(RetrievalFilterError, match="explicit test"):
        LexicalSearchAdapter().search(db_conn, query="học phí")
