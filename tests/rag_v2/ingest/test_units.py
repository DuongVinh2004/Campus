import ast
import json
from dataclasses import replace
from pathlib import Path

import pytest
from campus247.rag_v2.ingest.checks import check_units, coverage_stats
from campus247.rag_v2.ingest.units import (
    SOURCE_SEPARATOR,
    build_units,
    extract_scope,
    source_text,
)

ROOT = Path(__file__).resolve().parents[3]


def chunk(text, **kwargs):
    return dict(chunk_id="c", document_id="d", version_id="v", doc_title="Quy chế HUCE",
                doc_family="quy_che", section_label="", page=1, text=text, **kwargs)


@pytest.fixture(scope="module")
def corpus():
    rows = [json.loads(line) for line in (ROOT / "evals/corpus/served-chunks.jsonl").read_text(encoding="utf8").splitlines()]
    return rows, build_units(rows)


def test_real_corpus_lossless_and_bounded(corpus):
    rows, units = corpus
    assert not check_units(rows, units)
    stats = coverage_stats(rows, units)
    assert set(stats) == {"quy_che", "so_tay", "hoc_phi", "ctdt", "thong_bao", "khac"}
    assert all(s["min_chunk_coverage"] == 1 for s in stats.values())
    assert all(len(u.text) <= 1200 for u in units)
    assert {c["chunk_id"] for c in rows} == {c for u in units for c in u.chunk_ids}


def test_ids_stable_across_order_and_duplicate_provenance():
    a = chunk("Điều 14. Đăng ký học\n1. Điều kiện.\na) Điểm thứ nhất.\n2. Quy trình.")
    b = {**a, "chunk_id": "c2"}
    units = build_units([a, b])
    assert units == build_units([b, a])
    assert all(u.chunk_ids == ("c", "c2") for u in units)
    assert any("Điều 14 > Khoản 1 > Điểm a" in u.path for u in units)
    assert all("Điều 14. Đăng ký học" in u.text for u in units)
    assert not check_units([a, b], units)


def test_real_regulations_split_articles_and_clauses(corpus):
    _, units = corpus
    assert any(u.kind == "clause" and " > Khoản " in u.path and "Điều " in u.text for u in units if u.doc_family == "quy_che")


def test_real_table_rows_keep_headers_and_row_scope(corpus):
    _, units = corpus
    row = next(u for u in units if "K65 đến K68 | 592.500" in source_text(u))
    assert row.kind == "table_row"
    assert "Mức học phí (đồng)/tín chỉ (ĐVHT)" in row.text
    assert row.scope.cohorts == ("K65", "K66", "K67", "K68")
    assert row.scope.academic_years == ("2026-2027",)
    assert len(row.chunk_ids) >= 2


def test_scope_program_and_typographic_years():
    scope = extract_scope("HKI2026–2027; mã ngành 7480201; K69 đến K71")
    assert scope.programs == ("7480201",)
    assert scope.cohorts == ("K69", "K70", "K71")
    assert scope.academic_years == ("2026-2027",)


def test_ids_change_with_source_or_version_and_do_not_cross_documents():
    row = chunk("Điều 1. Văn bản.")
    first = build_units([row])[0]
    for change in ({"text": "Điều 1. Văn bản mới."}, {"version_id": "v2"}, {"document_id": "d2"}):
        assert build_units([{**row, **change}])[0].unit_id != first.unit_id


def test_long_handbook_contiguous_source_and_context():
    row = {**chunk("2.1 Đăng ký học\n" + "Sinh viên đọc hướng dẫn. " * 240), "doc_family": "so_tay"}
    units = build_units([row])
    assert len(units) > 2
    assert all(len(u.text) <= 1200 and "2.1 Đăng ký học" in u.text for u in units)
    assert not check_units([row], units)


def test_table_and_course_rows_are_distinct():
    row = {**chunk("Mã học phần | Tên | Tiên quyết\n471755 | CTDL 2 | 471754\n471757 | Đồ án | 471756\n"), "doc_family": "ctdt"}
    units = build_units([row])
    assert len(units) == 3
    assert all(u.kind == "table_row" for u in units)
    assert not check_units([row], units)


@pytest.mark.parametrize("mutation,code", [
    (lambda u: replace(u, text=""), "EMPTY_UNIT"),
    (lambda u: replace(u, text="invented text"), "NON_VERBATIM_UNIT"),
    (lambda u: replace(u, chunk_ids=("foreign",)), "UNKNOWN_CHUNK"),
    (lambda u: replace(u, chunk_ids=()), "MISSING_CHUNK_IDS"),
    (lambda u: replace(u, document_id="foreign"), "SOURCE_IDENTITY_MISMATCH"),
])
def test_checker_rejects_invalid_provenance(mutation, code):
    row = chunk("Điều 1. Nội dung nguyên văn.")
    unit = build_units([row])[0]
    assert code in {i.code for i in check_units([row], [mutation(unit)])}


def test_checker_duplicate_and_missing_coverage():
    row = chunk("Điều 1. Nội dung nguyên văn.")
    unit = build_units([row])[0]
    assert "DUPLICATE_UNIT_ID" in {i.code for i in check_units([row], [unit, unit])}
    assert "LOW_COVERAGE" in {i.code for i in check_units([row], [])}
    assert not check_units([row], [replace(unit, text="Điều 1. Nội dung nguyên văn.")])


def test_content_text_input_and_empty_chunk():
    row = {**chunk(""), "content_text": "Một đoạn nội dung."}
    assert not check_units([row], build_units([row]))
    assert build_units([chunk(" \n\t")]) == []


def test_reserved_marker_rejected():
    with pytest.raises(ValueError, match="RESERVED"):
        build_units([chunk("source" + SOURCE_SEPARATOR + "spoof")])


def test_v2_core_import_boundaries():
    base = ROOT / "services/api/src/campus247/rag_v2"
    for directory in (base / "ingest", base / "facts"):
        for path in directory.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf8"))):
                imports = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                assert not any(name.startswith(("campus247.infrastructure", "campus247.agent", "campus247.presentation")) for name in imports)
