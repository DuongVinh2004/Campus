"""The authorized index view is reused only for an identical authorized row set; any row change re-runs the checks."""
from types import SimpleNamespace

from campus247.agent.nodes import rag_v2 as node_module
from campus247.agent.nodes.rag_v2 import RagV2Node, _rows_fingerprint


def row(chunk, text="Sinh viên được bảo lưu.", sha="h", title="Quy chế"):
    return {"chunk_id": chunk, "evidence_sha256": sha, "source_id": "s", "document_version_id": "v", "title": title,
            "section_path": "Điều 1", "effective_from": "2026-01-01", "effective_until": None, "content_text": text}


def test_fingerprint_changes_with_every_field_the_checks_read():
    base = {"c1": row("c1"), "c2": row("c2")}
    same = {"c2": row("c2"), "c1": row("c1")}
    assert _rows_fingerprint(base) == _rows_fingerprint(same)          # order does not matter
    for change in ({"text": "Sinh viên không được bảo lưu."}, {"sha": "other"}, {"title": "Sổ tay"}):
        changed = dict(base, c1=row("c1", **change))
        assert _rows_fingerprint(changed) != _rows_fingerprint(base)
    assert _rows_fingerprint({"c1": row("c1")}) != _rows_fingerprint(base)   # a revoked row changes it
    expired = dict(base, c2=dict(row("c2"), effective_until="2026-02-01"))
    assert _rows_fingerprint(expired) != _rows_fingerprint(base)


def test_prepare_index_builds_once_per_row_set_and_again_after_a_change():
    built = []
    node = object.__new__(RagV2Node)
    node._build_index = lambda rows: (built.append(dict(rows)) or ("index", len(rows), {}))
    first = {"c1": row("c1")}
    assert node._prepare_index(first) == ("index", 1, {})
    assert node._prepare_index({"c1": row("c1")}) == ("index", 1, {})    # equal content, new dict: reused
    assert len(built) == 1
    node._prepare_index({"c1": row("c1", text="Đã sửa.")})
    assert len(built) == 2
