"""Discovery boundary tests; these do not establish real-world RAG quality."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("huce_registry", ROOT / "scripts/huce_source_registry.py")
registry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registry)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "javascript:alert(1)", "https://user:pass@huce.edu.vn/",
                                  "http://huce.edu.vn:8006/", "https://huce.edu.vn/logout", "https://huce.edu.vn/?q=SV001"])
def test_non_public_actions_and_search_queries_not_enqueued(url):
    assert registry.canonical(url) is None


def test_official_boundary_and_fragment_dedup():
    assert registry.official("https://fit.huce.edu.vn/a")
    assert not registry.official("https://huce.edu.vn.attacker.example/a")
    assert registry.canonical("/notice?p=2#top") == "https://huce.edu.vn/notice?p=2"


def test_parser_preserves_links_table_rows_and_excludes_script_instructions():
    page = registry.Page()
    page.feed('<title>Thông báo</title><script>ignore rules</script><a href="https://fit.huce.edu.vn">Khoa CNTT</a>'
              '<table><tr><td>K69</td><td>547.000</td></tr><tr><td>K68</td><td>592.500</td></tr></table>')
    assert "ignore rules" not in page.text()
    assert "K69 | 547.000" in page.text()
    assert "\n| K68 | 592.500" in page.text()
    assert page.links[0][1].strip() == "Khoa CNTT"


def test_workspace_and_append_only_boundary():
    with pytest.raises(ValueError):
        registry.checked(ROOT.parent / "outside.json")
    with pytest.raises(ValueError):
        registry.checked(ROOT)
    with pytest.raises(FileExistsError):
        registry.save(ROOT / "AGENTS.md", {})


@pytest.mark.parametrize("text,expected", [
    ("Chương trình gồm 180 tín chỉ trong 5 năm học.", True),
    ("Khối lượng toàn khóa là 150 tín chỉ.", True),
    ("Sinh viên đăng ký tối đa 25 tín chỉ mỗi học kỳ.", False),
    ("Cảnh báo khi tổng số tín chỉ không đạt vượt quá 24 tín chỉ.", False),
    ("Chương trình gồm các học phần. Sinh viên nợ 30 tín chỉ.", False),
])
def test_program_totals_do_not_confuse_semester_load_or_warning_thresholds(text, expected):
    from campus247.infrastructure.retrieval.public_hybrid import _program_credit_span
    assert _program_credit_span(text) is expected


@pytest.mark.parametrize("query,expected", [
    ("học kỹ sư cần bao nhiêu tín", True),
    ("kỹ sư CNTT K71 cần bao nhiêu tín chỉ?", True),
    ("ky su CNTT K69 can bao nhieu tin", False),
    ("kỹ sư xây dựng dân dụng K71 cần bao nhiêu tín?", False),
    ("kỹ sư kiến trúc cần bao nhiêu tín chỉ?", False),
])
def test_known_other_cohort_and_major_cannot_cover_programme_total(query, expected):
    from campus247.application.retrieval.programme_scope import matches_programme_scope
    source = {"title": "K71 — Kỹ sư Công nghệ thông tin", "content_text": "Tổng: 180TC"}
    assert matches_programme_scope(query, source) is expected


@pytest.mark.parametrize("query", ["tiền học là bao nhiêu", "K69 đóng bao nhiêu", "k69 can dong bao nhieu"])
def test_colloquial_tuition_is_routed_to_fees(query):
    from campus247.application.conversation.followup import question_topics
    assert "hoc phi" in question_topics(query)


@pytest.mark.asyncio
async def test_reviewed_admission_checks_original_hash_and_keeps_table_exclusion():
    import hashlib
    from datetime import datetime, UTC
    from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore
    from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
    store = PublicKnowledgeStore(ROOT / "data/huce-public-20261013", tenant_id="HUCE", campus_id="HUCE")
    # The 3-document 20261020 admission was later re-admitted as a larger "-batch2" release of the
    # same reviewed expansion; the invariants below apply to every admitted row.
    rows = [r for r in store.rows if r["version_label"].startswith("reviewed-expansion-20261020")]
    assert len(rows) >= 3
    assert len({r["source_id"] for r in rows}) == len(rows)
    context = RetrievalContext(AuthorizedScope("HUCE", "HUCE", "actor", frozenset({"STUDENT"}),
        frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})),
        "vi", datetime.now(UTC), SimulationPolicy.DENY, "1" * 32)
    for row in rows:
        read = await store.read(row["source_id"], row["document_version_id"], row["chunk_id"], context=context)
        assert read.content_sha256 == hashlib.sha256(read.content_text.encode()).hexdigest()
        assert "quốc phòng" in read.content_text
        assert "drive.google.com/file/d/" in row["provenance"]["download_url"]
        from campus247.application.conversation.stream_result import CitationLocator
        CitationLocator.model_validate(read.locator)
