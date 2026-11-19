"""DB-free contract tests; file writes use in-memory streams, no temp tree."""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("corpus_export", ROOT / "evals/runners/corpus_export.py")
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


def row(**changes):
    return {"chunk_id": UUID(int=1), "document_id": UUID(int=2), "version_id": UUID(int=3),
            "doc_title": "Quy chế đào tạo", "section_label": "Điều 5", "page": 2,
            "text": "  Điều kiện: 5 tín chỉ.\nGiữ nguyên dấu và khoảng trắng.  ",
            "password": "must-not-leak", "conversation": "must-not-leak", **changes}


def snapshot():
    return {"release_id": str(UUID(int=4)), "generation": 7, "policy_generation": 2,
            "as_of": "2026-10-28T00:00:00+00:00", "transaction_read_only": True,
            "selection": "test", "password": "must-not-leak"}


def test_exact_text_and_whitelisted_schema():
    original = row()
    result = export.normalize_row(original)
    assert tuple(result) == export.FIELDS
    assert result["chunk_id"] == str(original["chunk_id"])
    assert result["text"] == original["text"]
    assert result["doc_family"] == "quy_che"
    assert result["section_label"] == "Điều 5"
    assert result["page"] == 2
    assert "must-not-leak" not in json.dumps(result)
    assert export.normalize_row(row(page=None, section_label=None))["page"] is None


@pytest.mark.parametrize("title,family", [
    ("Chương trình đào tạo ngành CNTT", "ctdt"), ("CTĐT 2026", "ctdt"),
    ("Sổ tay sinh viên", "so_tay"), ("Thông báo học phí", "hoc_phi"),
    ("Quy định học vụ", "quy_che"), ("Thông báo đăng ký học", "thong_bao"),
    ("Dịch vụ thư viện", "khac"),
])
def test_family_labels(title, family):
    assert export.document_family(title) == family


@pytest.mark.parametrize("changes", [
    {"text": " \n\t"}, {"text": None}, {"doc_title": ""}, {"chunk_id": None},
    {"version_id": " "}, {"document_id": ""}, {"page": True}, {"page": 0},
    {"page": "2"}, {"section_label": ["a"]},
])
def test_invalid_rows_rejected(changes):
    with pytest.raises(ValueError):
        export.normalize_row(row(**changes))


def test_deterministic_utf8_jsonl_counts_and_hash():
    first = row()
    second = row(chunk_id=UUID(int=5), version_id=UUID(int=6))
    third = row(chunk_id=UUID(int=7), document_id=UUID(int=8), version_id=UUID(int=9))
    payload, manifest = export.serialize_corpus([third, second, first])
    assert export.serialize_corpus([first, second, third]) == (payload, manifest)
    records = [json.loads(line) for line in payload.decode("utf-8").splitlines()]
    assert len(records) == 3
    assert records[0]["text"] == first["text"]
    assert payload.endswith(b"\n") and not payload.startswith(b"\xef\xbb\xbf")
    assert manifest["chunk_count"] == 3
    assert manifest["version_count"] == 3
    assert manifest["document_count"] == 2
    assert manifest["sha256"] == hashlib.sha256(payload).hexdigest()
    assert manifest["matches_expected_counts"] is False


@pytest.mark.parametrize("rows,code", [([], "EMPTY_CORPUS"), ([row(), row()], "DUPLICATE_CHUNK_ID")])
def test_corpus_validation(rows, code):
    with pytest.raises(ValueError, match=code):
        export.serialize_corpus(rows)


def test_writer_exclusive_files_and_manifest(monkeypatch):
    paths = [MagicMock(), MagicMock()]
    streams = [io.BytesIO(), io.BytesIO()]
    for path, stream in zip(paths, streams):
        path.open.return_value.__enter__.return_value = stream
    monkeypatch.setattr(export, "export_paths", lambda: tuple(paths))
    manifest = export.write_export([row()], snapshot())
    for path in paths:
        path.open.assert_called_once_with("xb")
    payload, metadata = [stream.getvalue() for stream in streams]
    assert json.loads(payload)["text"] == row()["text"]
    assert json.loads(metadata) == manifest
    assert manifest["sha256"] == hashlib.sha256(payload).hexdigest()
    assert "must-not-leak" not in (payload + metadata).decode("utf-8")


def test_invalid_corpus_never_opens_destinations(monkeypatch):
    paths = MagicMock()
    monkeypatch.setattr(export, "export_paths", paths)
    with pytest.raises(ValueError, match="DUPLICATE_CHUNK_ID"):
        export.write_export([row(), row()], snapshot())
    paths.assert_not_called()


def test_existing_output_is_preserved(monkeypatch):
    monkeypatch.setattr(Path, "exists", lambda path: path.name == "manifest.json")
    with pytest.raises(FileExistsError, match="CORPUS_ALREADY_EXISTS"):
        export.export_paths()


def test_outside_workspace_is_rejected(monkeypatch):
    monkeypatch.setattr(export, "CORPUS", ROOT.parent / "outside-corpus")
    with pytest.raises(ValueError, match="CORPUS_OUTSIDE_WORKSPACE"):
        export.export_paths()


def fake_connection():
    conn = MagicMock()
    tx = conn.transaction.return_value
    tx.__aenter__ = AsyncMock()
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.fetchval = AsyncMock(side_effect=["on", datetime(2026, 10, 28, tzinfo=UTC)])
    conn.fetchrow = AsyncMock(return_value={key: snapshot()[key] for key in (
        "release_id", "generation", "policy_generation")})
    conn.fetch = AsyncMock(return_value=[row()])
    return conn


def test_database_readonly_snapshot_and_bindings():
    conn = fake_connection()
    relation = "FROM public_chunks c WHERE release_id=$9 AND tenant_id=$10 AND at_time=$3"
    rows, metadata = asyncio.run(export.read_served_rows(conn, tenant="test-tenant", relation=relation))
    conn.transaction.assert_called_once_with(isolation="repeatable_read", readonly=True)
    assert rows == [row()]
    assert metadata["transaction_read_only"] is True
    sql, release, tenant, as_of, campus = conn.fetch.call_args.args
    assert "release_id=$1 AND tenant_id=$2 AND at_time=$3" in sql
    assert (release, tenant, as_of, campus) == (
        snapshot()["release_id"], "test-tenant", datetime(2026, 10, 28, tzinfo=UTC), "HUCE")
    assert all("SELECT" in call.args[0] or "SHOW" in call.args[0]
               for method in (conn.fetch, conn.fetchrow, conn.fetchval) for call in method.call_args_list)
    conn.execute.assert_not_called()


@pytest.mark.parametrize("failure", ["readwrite", "missing_pointer"])
def test_unsafe_or_missing_snapshot_stops_before_chunk_read(failure):
    conn = fake_connection()
    if failure == "readwrite":
        conn.fetchval.side_effect = ["off"]
    else:
        conn.fetchrow.return_value = None
    with pytest.raises((RuntimeError, ValueError)):
        asyncio.run(export.read_served_rows(conn, tenant="test", relation="unused"))
    conn.fetch.assert_not_called()


def test_cli_redacts_exception_details(monkeypatch, capsys):
    async def failed():
        raise OSError("password=must-not-leak")
    monkeypatch.setattr(export, "run", failed)
    assert export.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "CORPUS_EXPORT_FAILED: OSError\n"


def test_scope_union_keeps_serving_guards():
    relation = """FROM members rm WHERE rm.release_id=$9 AND x.tenant_id=$10
        AND v.effective_from<=$3 AND s.campus_scope=$4
        AND s.faculty_scope && $5::varchar[] AND s.program_scope && $6::varchar[]
        AND s.audiences && $7::varchar[] AND NOT s.is_synthetic
        AND ($8::boolean OR NOT s.is_synthetic)
        AND ($11::boolean OR v.status='PUBLISHED')"""
    query = export.corpus_query(relation)
    assert "s.faculty_scope && s.faculty_scope::varchar[]" in query
    assert "s.program_scope && s.program_scope::varchar[]" in query
    assert "s.audiences && s.audiences::varchar[]" in query
    assert "v.effective_from<=$3 AND s.campus_scope=$4" in query
    assert "rm.release_id=$1 AND x.tenant_id=$2" in query
    assert "(FALSE::boolean OR v.status='PUBLISHED')" in query
    assert "AND NOT s.is_synthetic" in query


@pytest.mark.parametrize("matched,code", [(True, 0), (False, 0)])
def test_cli_count_mismatch_is_only_a_historical_reference(monkeypatch, capsys, matched, code):
    async def completed():
        return {"chunk_count": 1, "version_count": 1, "document_count": 1,
                "sha256": "a" * 64, "matches_expected_counts": matched}
    monkeypatch.setattr(export, "run", completed)
    assert export.main() == code
    captured = capsys.readouterr()
    assert json.loads(captured.out)["matches_expected_counts"] is matched
    # New documents legitimately change the counts; the historical baseline is informational.
    assert ("CORPUS_HISTORICAL_REFERENCE" in captured.err) is (not matched)
