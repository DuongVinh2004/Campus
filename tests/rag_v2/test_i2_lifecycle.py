"""I2 gates: offline transports, synthetic releases and exact source assertions."""
import asyncio
import importlib.util
import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from datetime import UTC, datetime

import httpx
import numpy as np
import pytest

from campus247.bootstrap import rag_v2 as boot
from campus247.rag_v2.adapters.index_store import IndexSnapshot, read_index, write_index
from campus247.rag_v2.facts.extract import extract_facts
from campus247.rag_v2.ingest.checks import check_units
from campus247.rag_v2.ingest.units import build_units, context_text, source_text
from evals.runners import corpus_export as export

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("i2_builder", ROOT / "scripts/rag_v2_build_index.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    monkeypatch.setattr(builder, "CACHE_PATH", MagicMock())
    monkeypatch.setattr(builder, "USE_CACHE", False)
    monkeypatch.setattr(builder, "_CACHE", {})


def chunk(text="Nội dung D1", key="c1", **extra):
    return dict(chunk_id=key, document_id=key, version_id="v1", doc_title="Tài liệu",
                text=text, section_label=None, page=1, **extra)


def identity(revision="rev", **extra):
    return dict(embedding_model="BAAI/bge-m3", embedding_revision=revision,
                embedding_pooling="cls", normalization="L2", **extra)


def transport(revision="rev", status=200, calls=None, pooling="cls"):
    def handler(request):
        if request.url.path == "/info":
            return httpx.Response(200, json=dict(model_id="BAAI/bge-m3", model_sha=revision,
                model_type={"embedding": {}}, auto_truncate=False, pooling=pooling))
        texts = json.loads(request.content)["inputs"]
        if calls is not None:
            calls.extend(texts)
        return httpx.Response(status, json=[[0., 1.] for _ in texts] if status == 200 else {"error": "too many tokens"})
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://fake")


@pytest.mark.parametrize("suffix", [" KHÔNG", " 700.000", " ngoại trừ"])
def test_coverage_rejects_small_semantic_loss(suffix):
    row = chunk("Nội dung " + "x" * 600 + suffix)
    unit = build_units([row])[0]
    assert check_units([row], [replace(unit, text=source_text(unit)[:-len(suffix)])])


def test_coverage_requires_each_repeated_occurrence():
    row = chunk("Điều 1. Giữ nguyên.\nĐiều 1. Giữ nguyên.\n")
    units = build_units([row])
    assert not check_units([row], units)
    assert check_units([row], units[:1])


@pytest.mark.parametrize("text,basis", [
    ("STT | Học phí (đồng/tín chỉ) | Chương trình\n1 | 700.000 | Alpha", "tín chỉ"),
    ("Ngành | Đơn giá mỗi tín chỉ | Nhóm áp dụng\nAlpha | 700.000 | K72", "tín chỉ"),
    ("Chương trình | Mức thu (đồng/ĐVHT)\nAlpha | 700.000", "ĐVHT"),
    ("Chương trình | Học phí\n | đồng/năm\nAlpha | 700.000", "năm"),
    ("Chương trình | Học phí (đồng/tín chỉ)\nAlpha | 700.000\n | 800.000", "tín chỉ"),
    ("Chương trình | Đơn giá\n | mỗi tín chỉ\nAlpha | 700.000", "tín chỉ"),
    ("Chương trình | Học phí năm 2026 (đồng/tín chỉ)\nAlpha | 700.000", "tín chỉ"),
])
def test_table_metamorphisms(text, basis):
    units = build_units([chunk(text)])
    fees = [f for f in extract_facts(units) if f.kind == "fee"]
    assert fees and all(f.subject == "Alpha" and f.attributes["basis"] == basis for f in fees)
    assert len(fees) == (2 if "800.000" in text else 1)
    assert all(f.quote in text and f.value in f.quote for f in fees)
    assert not check_units([chunk(text)], units)


def test_unknown_fee_schema_does_not_guess_basis_from_row():
    units = build_units([chunk("Ngành | Học phí\nAlpha tín chỉ | 700.000")])
    assert not [f for f in extract_facts(units) if f.kind == "fee"]


def test_horizontal_header_span_keeps_column_paths():
    text = "Chương trình | Học phí | \n | đồng/tín chỉ | đồng/năm\nAlpha | 700.000 | 900.000"
    fees = [f for f in extract_facts(build_units([chunk(text)])) if f.kind == "fee"]
    assert {(f.subject, f.value, f.attributes["basis"]) for f in fees} == {
        ("Alpha", "700.000", "tín chỉ"), ("Alpha", "900.000", "năm")}


@pytest.mark.parametrize("revision,pooling", [("new", "cls"), ("rev", "mean")])
def test_cache_is_bound_to_identity(monkeypatch, revision, pooling):
    monkeypatch.setattr(builder, "USE_CACHE", True)
    monkeypatch.setattr(builder, "_CACHE", {})
    monkeypatch.setattr(builder, "_append_cache", lambda *args: None, raising=False)
    units = build_units([chunk()])
    with transport() as client:
        builder.embed_units(units, client=client)
    calls = []
    with transport(revision, calls=calls, pooling=pooling) as client:
        builder.embed_units(units, client=client)
    assert calls == [units[0].text]


def test_cache_only_embeds_misses_and_ignores_legacy(monkeypatch):
    monkeypatch.setattr(builder, "USE_CACHE", True)
    units = build_units([chunk(), chunk("Nội dung D2", "c2")])
    monkeypatch.setattr(builder, "_CACHE", {sha256(units[0].text.encode()).hexdigest(): [1., 0.]})
    monkeypatch.setattr(builder, "_append_cache", lambda *args: None, raising=False)
    with transport() as client:
        builder.embed_units(units[:1], client=client)
    calls = []
    with transport(calls=calls) as client:
        builder.embed_units(units, client=client)
    assert calls == [units[1].text]


@pytest.mark.parametrize("status", [413, 503])
def test_embedding_failure_never_shortens_input(monkeypatch, status):
    monkeypatch.setattr(builder.time, "sleep", lambda _: None)
    calls = []
    units = build_units([chunk("Văn bản rất dài " * 60)])
    with transport(status=status, calls=calls) as client, pytest.raises((httpx.HTTPStatusError, ValueError)):
        builder.embed_units(units, client=client)
    assert calls and set(calls) == {units[0].text}


def snapshot(units, **extra):
    manifest = dict(identity(), embedding_status="complete", embedding_dimension=2,
                    unit_count=len(units), release_id="r1", generation=1, policy_generation=0,
                    chunk_inventory={c: sha256(source_text(u).encode()).hexdigest()
                                     for u in units for c in u.chunk_ids}, **extra)
    return IndexSnapshot(tuple(units), (), np.array([[1., 0.]] * len(units), dtype=np.float32), manifest)


def runtime():
    profile = SimpleNamespace(model_id="BAAI/bge-m3", model_revision="rev", dimension=2, normalization="l2")
    return SimpleNamespace(embedding=SimpleNamespace(profile=profile),
        current={"release_id": "r1", "generation": 1, "policy_generation": 0},
        rag_v2_revalidate=lambda *a: None, rag_v2_sources=lambda *a: None)


@pytest.mark.parametrize("field,value", [("embedding_status", "pending"), ("embedding_model", "OTHER"),
    ("embedding_revision", "old"), ("embedding_dimension", 3)])
def test_startup_rejects_incompatible_snapshot(monkeypatch, field, value):
    saved = snapshot(build_units([chunk()]))
    saved.manifest[field] = value
    monkeypatch.setattr(boot, "read_index", lambda _: saved)
    with pytest.raises(ValueError, match="RAG_V2"):
        boot.load_rag_v2(SimpleNamespace(rag_v2_index_dir=ROOT), gateway=None, knowledge_runtime=runtime())


def test_release_lifecycle_incremental_and_stale(monkeypatch):
    first = chunk()
    releases = [[first], [first, chunk("D2 mới", "c2")],
                [chunk("D1 thay thế"), chunk("D2 mới", "c2")],
                [chunk("D2 mới", "c2")]]
    base = None
    for generation, rows in enumerate(releases, 1):
        units = build_units(rows)
        calls = []
        with transport(calls=calls) as client:
            matrix, metadata = builder.embed_units(units, client=client, base=base,
                chunk_inventory=builder.chunk_inventory(rows))
        assert len(calls) == (1 if generation in (1, 2, 3) else 0)
        manifest = dict(metadata, chunk_inventory=builder.chunk_inventory(rows),
            release_id=f"r{generation}", generation=generation, policy_generation=0,
            embedding_status="complete", embedding_dimension=2, unit_count=len(units))
        saved = IndexSnapshot(tuple(units), (), matrix, manifest)
        rt = runtime()
        rt.current = {k: manifest[k] for k in ("release_id", "generation", "policy_generation")}
        inventory = {"chunk_inventory": manifest["chunk_inventory"], **rt.current}
        monkeypatch.setattr(boot, "read_index", lambda _, s=saved: s)
        node = boot.load_rag_v2(SimpleNamespace(rag_v2_index_dir=ROOT), gateway=None,
            knowledge_runtime=rt, inventory_reader=lambda: inventory)
        assert not asyncio.run(node.rag_v2_status.refresh())["stale"]
        inventory = {**inventory, "chunk_inventory": {**inventory["chunk_inventory"], "future": "a" * 64}}
        state = asyncio.run(node.rag_v2_status.refresh())
        assert state["stale"] and state["missing_chunks"] == 1 and state["warm"] is None
        if generation > 1:
            assert any("D2 mới" in u.text for u in saved.units)
        base = saved


def test_export_cli_new_generation_is_not_historical_failure(monkeypatch):
    async def run(**kwargs):
        return dict(chunk_count=1, version_count=1, document_count=1, sha256="a" * 64,
                    matches_expected_counts=False)
    monkeypatch.setattr(export, "run", run)
    assert export.main(["--output-dir", "data/i2-export-new"]) == 0


def test_manifest_inventory_checked_on_read(tmp_path):
    units = build_units([chunk()])
    write_index(tmp_path / "snapshot", units, [], np.array([[1., 0.]], dtype=np.float32),
        dict(identity(), chunk_inventory={"wrong": "a" * 64}))
    with pytest.raises(ValueError, match="INVENTORY"):
        read_index(tmp_path / "snapshot")


def test_inventory_hash_must_match_reconstructed_source(tmp_path):
    units = build_units([chunk()])
    write_index(tmp_path / "bad-hash", units, [], np.array([[1., 0.]], dtype=np.float32),
                dict(identity(), chunk_inventory={"c1": "b" * 64}))
    with pytest.raises(ValueError, match="INVENTORY"):
        read_index(tmp_path / "bad-hash")


@pytest.mark.parametrize("changes,expected", [
    ({"c2": "a" * 64}, (1, 1, 0)),
    ({}, (0, 1, 0)),
    ({"c1": "b" * 64}, (0, 0, 1)),
])
def test_readiness_inventory_counts(changes, expected):
    saved = snapshot(build_units([chunk()]))
    current = {"release_id": "r1", "generation": 1, "policy_generation": 0,
               "chunk_inventory": changes}
    state = asyncio.run(boot.RagV2Status(saved.manifest, runtime(), lambda: current).refresh())
    assert (state["missing_chunks"], state["extra_chunks"], state["changed_chunks"]) == expected
    assert state["snapshot_state"] == "stale"


@pytest.mark.parametrize("enabled,stale,code", [(False, False, 200), (True, False, 200), (True, True, 503)])
def test_health_reports_v2_without_enabling_it(enabled, stale, code):
    from starlette.requests import Request
    from campus247.presentation.health import get_readiness
    saved = snapshot(build_units([chunk()]))
    current = dict(runtime().current, chunk_inventory=saved.manifest["chunk_inventory"])
    if stale:
        current["generation"] = 9
    state = SimpleNamespace()
    if enabled:
        state.rag_v2_node = SimpleNamespace(rag_v2_status=boot.RagV2Status(saved.manifest, runtime(), lambda: current))
    request = Request({"type": "http", "app": SimpleNamespace(state=state)})
    response = asyncio.run(get_readiness(request))
    payload = json.loads(response.body)
    assert response.status_code == code
    assert payload["rag_v2"]["enabled"] is enabled
    assert payload["rag_v2"]["warm"] is None
    assert payload["rag_v2"]["stale"] is stale


def test_export_two_immutable_generations_with_readonly_fake(tmp_path):
    from unittest.mock import AsyncMock
    manifests = []
    for generation in (1, 2):
        conn = MagicMock()
        conn.transaction.return_value.__aenter__ = AsyncMock()
        conn.transaction.return_value.__aexit__ = AsyncMock(return_value=False)
        conn.fetchval = AsyncMock(side_effect=["on", datetime(2026, 10, 31, tzinfo=UTC)])
        conn.fetchrow = AsyncMock(return_value=dict(release_id=f"r{generation}", generation=generation, policy_generation=0))
        conn.fetch = AsyncMock(return_value=[chunk(key=f"c{i}") for i in range(generation)])
        rows, metadata = asyncio.run(export.read_served_rows(conn, tenant="fake", relation="FROM chunks c"))
        directory = tmp_path / f"export-{generation}"
        manifests.append(export.write_export(rows, metadata, output_dir=directory))
        before = {p.name: p.read_bytes() for p in directory.iterdir()}
        with pytest.raises(FileExistsError):
            export.write_export(rows, metadata, output_dir=directory)
        assert before == {p.name: p.read_bytes() for p in directory.iterdir()}
        conn.transaction.assert_called_once_with(isolation="repeatable_read", readonly=True)
        conn.execute.assert_not_called()
    assert [m["snapshot"]["generation"] for m in manifests] == [1, 2]


def test_cli_incremental_snapshots_and_failure_are_immutable(monkeypatch, tmp_path):
    monkeypatch.setattr(builder, "_append_cache", lambda *args: None)
    base = None
    for generation, rows in enumerate(([chunk("\n\nĐiều 1. Nội dung D1")], [chunk("\n\nĐiều 1. Nội dung D1"), chunk("D2", "c2")]), 1):
        monkeypatch.setattr(builder, "_CACHE", {})
        corpus_dir = tmp_path / f"corpus-{generation}"
        exported = export.write_export(rows, dict(release_id=f"r{generation}", generation=generation,
            policy_generation=0, as_of="2026-10-31", transaction_read_only=True, selection="fake"), output_dir=corpus_dir)
        output = tmp_path / f"index-{generation}"
        calls = []
        original = builder.embed_units
        with transport(calls=calls) as client:
            monkeypatch.setattr(builder, "embed_units", lambda units, **kwargs: original(units, client=client, **kwargs))
            args = ["--corpus", str(corpus_dir / "served-chunks.jsonl"), "--output", str(output), "--embed"]
            if base:
                args += ["--base", str(base)]
            assert builder.main(args) == 0
        monkeypatch.setattr(builder, "embed_units", original)
        saved = read_index(output)
        assert saved.manifest["release_id"] == exported["snapshot"]["release_id"]
        assert len(calls) == 1
        before = {p.name: p.read_bytes() for p in output.iterdir()}
        with pytest.raises(SystemExit):
            builder.main(args)
        assert before == {p.name: p.read_bytes() for p in output.iterdir()}
        base = output
    monkeypatch.setattr(builder.time, "sleep", lambda _: None)
    monkeypatch.setattr(builder, "_CACHE", {})
    output = tmp_path / "failed"
    with transport(status=503) as client:
        monkeypatch.setattr(builder, "embed_units", lambda units, **kwargs: original(units, client=client, **kwargs))
        with pytest.raises(httpx.HTTPStatusError):
            builder.main(["--corpus", str(corpus_dir / "served-chunks.jsonl"), "--output", str(output), "--embed"])
    assert not output.exists()


def test_transient_503_retries_full_input(monkeypatch):
    monkeypatch.setattr(builder.time, "sleep", lambda _: None)
    requests = []
    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(503 if len(requests) == 1 else 200, json=[[1., 0.]])
    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://fake") as client:
        assert builder._embed_batch(client, ["x" * 1000]) == [[1., 0.]]
    assert requests[0] == requests[1]


def test_inventory_reconstructs_every_exported_chunk():
    from campus247.rag_v2.adapters.index_store import _unit_inventory, inventory_gaps
    rows = [json.loads(line) for line in (ROOT / "evals/corpus/served-chunks.jsonl").read_text(encoding="utf8").splitlines()]
    units = build_units(rows)
    expected = {r["chunk_id"]: sha256(r["text"].encode()).hexdigest() for r in rows}
    assert _unit_inventory(units, inventory_gaps(rows, units)) == expected


@pytest.mark.parametrize("field", ["embedding_model", "embedding_revision", "embedding_pooling", "normalization"])
def test_cache_key_covers_every_embedding_setting(field):
    original = identity()
    changed = {**original, field: "different"}
    assert builder._cache_key(original, "full text") != builder._cache_key(changed, "full text")
    assert builder._cache_key(original, "full text") != builder._cache_key(original, "full")


@pytest.mark.parametrize("field,value", [("release_id", "new"), ("generation", 9),
    ("embedding_revision", "new"), ("chunk_inventory", {"c1": "b" * 64})])
def test_read_index_rejects_modified_binding(tmp_path, field, value):
    directory = tmp_path / "binding"
    write_index(directory, build_units([chunk()]), [], np.array([[1., 0.]], dtype=np.float32), identity())
    path = directory / "manifest.json"
    data = json.loads(path.read_text(encoding="utf8"))
    data[field] = value
    # Deliberately mutate this test's own synthetic manifest, never an old snapshot.
    path.write_text(json.dumps(data), encoding="utf8")
    with pytest.raises(ValueError, match="BINDING"):
        read_index(directory)
