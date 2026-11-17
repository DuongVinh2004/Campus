"""Exclusive, workspace-local v2 index snapshots; no existing files are replaced."""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

import numpy as np
from campus247.rag_v2.adapters.npy import load_matrix
from campus247.rag_v2.ingest.units import SPAN, SPLITTER_VERSION, context_text, source_text
from campus247.rag_v2.types import Fact, Scope, Unit

ROOT = Path(__file__).resolve().parents[6]
FILES = ("units.jsonl", "facts.jsonl", "embeddings.npy", "manifest.json")


@dataclass(frozen=True)
class IndexSnapshot:
    units: tuple[Unit, ...]
    facts: tuple[Fact, ...]
    embeddings: np.ndarray
    manifest: Mapping[str, object]


def _directory(directory: str | Path) -> Path:
    candidate = Path(directory)
    if ".." in candidate.parts or any(c in str(candidate) for c in "*?{}"):
        raise ValueError("AMBIGUOUS_INDEX_PATH")
    resolved = candidate.resolve()
    if resolved == ROOT or not resolved.is_relative_to(ROOT):
        raise ValueError("INDEX_OUTSIDE_WORKSPACE")
    return resolved


def chunk_inventory(chunks) -> dict[str, str]:
    inventory = {}
    for chunk in chunks:
        key = str(chunk["chunk_id"])
        value = sha256(chunk.get("content_text", chunk.get("text", "")).encode("utf-8")).hexdigest()
        if key in inventory:
            raise ValueError("DUPLICATE_CORPUS_CHUNK")
        inventory[key] = value
    return inventory


def _source_spans(units):
    spans = {}
    for unit in units:
        match = SPAN.search(context_text(unit))
        for key in unit.chunk_ids:
            start = int(match[1]) if match else 0
            body = source_text(unit)
            if match and int(match[2]) - start != len(body):
                raise ValueError("INDEX_SOURCE_SPAN_MISMATCH")
            prior = spans.setdefault(key, {}).get(start)
            if prior is not None and prior != body:
                raise ValueError("INDEX_SOURCE_SPAN_MISMATCH")
            spans[key][start] = body
    return spans


def inventory_gaps(chunks, units):
    """Retain only omitted nonsemantic spans so exact chunk hashes can be checked."""
    spans, result = _source_spans(units), {}
    for chunk in chunks:
        key, cursor = str(chunk["chunk_id"]), 0
        text = chunk.get("content_text", chunk.get("text", ""))
        gaps = []
        for start, body in sorted(spans.get(key, {}).items()):
            if start > cursor:
                gaps.append([cursor, text[cursor:start]])
            cursor = start + len(body)
        if cursor < len(text):
            gaps.append([cursor, text[cursor:]])
        if any(any(c.isalnum() for c in body) for _, body in gaps):
            raise ValueError("INDEX_SEMANTIC_GAP")
        if gaps:
            result[key] = gaps
    return result


def _unit_inventory(units, gaps=None):
    spans = _source_spans(units)
    for key, fragments in (gaps or {}).items():
        if key not in spans:
            raise ValueError("INDEX_INVENTORY_MISMATCH")
        for start, text in fragments:
            if type(start) is not int or start < 0 or not isinstance(text, str) or any(c.isalnum() for c in text) or start in spans[key]:
                raise ValueError("INDEX_INVENTORY_GAP_INVALID")
            spans[key][start] = text
    inventory = {}
    for key, parts in spans.items():
        cursor, text = 0, []
        for start, body in sorted(parts.items()):
            if start != cursor:
                raise ValueError("INDEX_INVENTORY_SPAN_GAP")
            text.append(body)
            cursor += len(body)
        inventory[key] = sha256("".join(text).encode()).hexdigest()
    return inventory


def _manifest_hash(metadata):
    return sha256(json.dumps({k: v for k, v in metadata.items() if k != "binding_sha256"},
        sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _validate_inventory(units, metadata):
    expected = metadata.get("chunk_inventory")
    keys = {key for unit in units for key in unit.chunk_ids}
    if (not isinstance(expected, dict) or set(expected) != keys
            or any(not isinstance(v, str) or not re.fullmatch(r"[a-f0-9]{64}", v) for v in expected.values())
            or metadata.get("chunk_count", len(expected)) != len(expected)):
        raise ValueError("INDEX_INVENTORY_MISMATCH")
    if expected != _unit_inventory(units, metadata.get("chunk_gaps")):
        raise ValueError("INDEX_INVENTORY_MISMATCH")


def _scope(data: dict) -> Scope:
    return Scope(**{k: tuple(v) for k, v in data.items()})


def _unit(data: dict) -> Unit:
    return Unit(**{**data, "chunk_ids": tuple(data["chunk_ids"]), "scope": _scope(data.get("scope", {}))})


def _fact(data: dict) -> Fact:
    return Fact(**{**data, "scope": _scope(data.get("scope", {}))})


def normalize_embeddings(values, count: int) -> np.ndarray:
    matrix = np.asarray(values, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[0] != count or not np.isfinite(matrix).all():
        raise ValueError("INVALID_EMBEDDING_MATRIX")
    if matrix.shape[1] == 0:
        return matrix
    norms = np.linalg.norm(matrix.astype(np.float64), axis=1, keepdims=True)
    if (norms <= 0).any():
        raise ValueError("ZERO_EMBEDDING")
    return (matrix / norms).astype(np.float32)


def _validate(units, facts, embeddings):
    ids = {u.unit_id: u for u in units}
    if len(ids) != len(units) or len({f.fact_id for f in facts}) != len(facts):
        raise ValueError("DUPLICATE_INDEX_ID")
    for fact in facts:
        unit = ids.get(fact.unit_id)
        if unit is None or not fact.value or fact.value not in fact.quote or not fact.quote or fact.quote not in source_text(unit):
            raise ValueError("INVALID_FACT_PROVENANCE")
    matrix = np.asarray(embeddings)
    if matrix.dtype != np.float32 or matrix.ndim != 2 or matrix.shape[0] != len(units) or not np.isfinite(matrix).all():
        raise ValueError("INVALID_EMBEDDING_MATRIX")
    if matrix.shape[1] and not np.allclose(np.linalg.norm(matrix, axis=1), 1, atol=1e-5):
        raise ValueError("EMBEDDINGS_NOT_NORMALIZED")


def write_index(directory: str | Path, units: Sequence[Unit], facts: Sequence[Fact],
                embeddings: np.ndarray, manifest: Mapping[str, object]) -> IndexSnapshot:
    directory = _directory(directory)
    destinations = [directory / name for name in FILES]
    if any(p.exists() or p.is_symlink() for p in destinations):
        raise FileExistsError("INDEX_ALREADY_EXISTS; select a new output directory")
    _validate(units, facts, embeddings)
    metadata = dict(manifest)
    if "chunk_inventory" not in metadata:
        metadata["chunk_inventory"] = _unit_inventory(units, metadata.get("chunk_gaps"))
    metadata.setdefault("splitter_version", SPLITTER_VERSION)
    for key in ("release_id", "generation", "policy_generation", "embedding_model", "embedding_revision", "embedding_pooling"):
        metadata.setdefault(key, None)
    metadata.update(schema_version=2, unit_count=len(units), fact_count=len(facts),
                    embedding_dimension=embeddings.shape[1],
                    embedding_status="complete" if embeddings.shape[1] else "pending",
                    normalization="L2", dtype="float32")
    directory.mkdir(parents=True, exist_ok=True)
    # Recheck resolved destinations after directory creation; do not follow links.
    if any(p.resolve().parent != directory or p.is_symlink() for p in destinations):
        raise ValueError("INDEX_DESTINATION_CHANGED")
    for name, rows in (("units.jsonl", units), ("facts.jsonl", facts)):
        with (directory / name).open("x", encoding="utf-8", newline="\n") as stream:
            for row in rows:
                stream.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")
    with (directory / "embeddings.npy").open("xb") as stream:
        np.save(stream, embeddings, allow_pickle=False)
    metadata["files_sha256"] = {name: sha256((directory / name).read_bytes()).hexdigest() for name in FILES[:-1]}
    metadata["binding_sha256"] = _manifest_hash(metadata)
    with (directory / "manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    return IndexSnapshot(tuple(units), tuple(facts), embeddings, metadata)


def read_index(directory: str | Path) -> IndexSnapshot:
    directory = _directory(directory)
    if any((directory / name).is_symlink() or (directory / name).resolve().parent != directory for name in FILES):
        raise ValueError("INDEX_SYMLINK")
    metadata = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if metadata.get("binding_sha256") != _manifest_hash(metadata):
        raise ValueError("INDEX_MANIFEST_BINDING_MISMATCH")
    for name in FILES[:-1]:
        if sha256((directory / name).read_bytes()).hexdigest() != metadata["files_sha256"][name]:
            raise ValueError("INDEX_CHECKSUM_MISMATCH")
    units = tuple(_unit(json.loads(line)) for line in (directory / "units.jsonl").read_text(encoding="utf-8").splitlines())
    facts = tuple(_fact(json.loads(line)) for line in (directory / "facts.jsonl").read_text(encoding="utf-8").splitlines())
    embeddings = load_matrix(directory / "embeddings.npy")
    _validate(units, facts, embeddings)
    if (metadata.get("unit_count"), metadata.get("fact_count"), metadata.get("embedding_dimension")) != (len(units), len(facts), embeddings.shape[1]):
        raise ValueError("INDEX_MANIFEST_MISMATCH")
    expected_status = "complete" if embeddings.shape[1] else "pending"
    if metadata.get("embedding_status") != expected_status:
        raise ValueError("INDEX_EMBEDDING_STATUS_MISMATCH")
    _validate_inventory(units, metadata)
    if metadata.get("schema_version") != 2 or metadata.get("splitter_version") != SPLITTER_VERSION:
        raise ValueError("INDEX_SPLITTER_VERSION_MISMATCH")
    return IndexSnapshot(units, facts, embeddings, metadata)
