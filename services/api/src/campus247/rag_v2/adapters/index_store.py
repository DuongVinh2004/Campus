"""Exclusive, workspace-local v2 index snapshots; no existing files are replaced."""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

import numpy as np
from campus247.rag_v2.adapters.npy import load_matrix
from campus247.rag_v2.ingest.units import source_text
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
    metadata.update(schema_version=1, unit_count=len(units), fact_count=len(facts),
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
    with (directory / "manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    return IndexSnapshot(tuple(units), tuple(facts), embeddings, metadata)


def read_index(directory: str | Path) -> IndexSnapshot:
    directory = _directory(directory)
    if any((directory / name).is_symlink() or (directory / name).resolve().parent != directory for name in FILES):
        raise ValueError("INDEX_SYMLINK")
    metadata = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
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
    return IndexSnapshot(units, facts, embeddings, metadata)
