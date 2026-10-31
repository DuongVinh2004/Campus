"""Build a fresh index. Add --embed for the local BGE-m3 server; never overwrite."""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from collections import Counter
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api/src"))
sys.path.insert(0, str(ROOT))

import httpx
import numpy as np
from campus247.rag_v2.adapters.index_store import (
    normalize_embeddings,
    chunk_inventory,
    inventory_gaps,
    read_index,
    write_index,
)
from campus247.rag_v2.facts.extract import extract_facts
from campus247.rag_v2.ingest.checks import check_units, coverage_stats
from campus247.rag_v2.ingest.units import SPLITTER_VERSION, build_units

from evals.runners.corpus_export import normalize_row


CACHE_PATH = ROOT / "data" / "rag_v2_index" / "embed-cache.jsonl"
_CACHE: dict = {}
USE_CACHE = False  # the CLI turns the resume cache on; library callers and tests never touch it
if CACHE_PATH.exists():
    for _line in CACHE_PATH.read_text(encoding="utf-8").splitlines():
        try:
            _row = json.loads(_line)
            if _row.get("identity") and _row.get("text_sha256"):
                _CACHE[_row["k"]] = _row
            else:
                warnings.warn("LEGACY_EMBED_CACHE_IGNORED", stacklevel=1)
        except (ValueError, KeyError):
            pass


class EmbeddingInputTooLong(ValueError):
    """The entire unit must fit; no prefix vector can activate a snapshot."""


def _embed_batch(client, texts):
    """Retry service unavailability with exactly the same full inputs."""
    for attempt in range(8):
        response = client.post("/embed", json={"inputs": texts, "normalize": True, "truncate": False})
        if response.status_code == 200:
            rows = response.json()
            if not isinstance(rows, list) or len(rows) != len(texts):
                raise ValueError("EMBEDDING_BATCH_COUNT_MISMATCH")
            return rows
        if response.status_code in (400, 413, 422):
            raise EmbeddingInputTooLong("EMBEDDING_INPUT_REJECTED")
        if response.status_code != 503:
            response.raise_for_status()
        if attempt < 7:
            time.sleep(2 + 3 * attempt)
    response.raise_for_status()


def _append_cache(entries):
    from campus247.rag_v2.adapters.index_store import _directory
    directory = _directory(CACHE_PATH.parent)
    path = directory / CACHE_PATH.name
    if path.is_symlink() or path.resolve().parent != directory:
        raise ValueError("INVALID_CACHE_PATH")
    directory.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")


def _cache_key(identity, text):
    return sha256(json.dumps([identity, text], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def embed_units(units, *, batch_size=20, client=None, base=None, chunk_inventory=None):
    if not 1 <= batch_size <= 20:
        raise ValueError("BATCH_SIZE_MUST_BE_1_TO_20")
    if client is None:
        with httpx.Client(base_url="http://127.0.0.1:18081", timeout=120, trust_env=False, follow_redirects=False) as active:
            return embed_units(units, batch_size=batch_size, client=active, base=base, chunk_inventory=chunk_inventory)
    info_response = client.get("/info")
    info_response.raise_for_status()
    info = info_response.json()
    if (str(info.get("model_id", "")).casefold() != "baai/bge-m3"
            or set(info.get("model_type", {})) != {"embedding"}
            or info.get("auto_truncate") is not False):
        raise ValueError("LOCAL_BGE_M3_IDENTITY_REJECTED")
    revision = info.get("model_sha")
    if revision is not None and (not isinstance(revision, str) or not revision.strip()):
        raise ValueError("EMBEDDING_REVISION_REQUIRED")
    # Missing revisions can be inspected in library probes, but never cached or
    # activated: bootstrap requires a nonempty exact revision.
    identity = {"embedding_model": info["model_id"], "embedding_revision": revision,
                "embedding_pooling": info.get("pooling", info.get("model_type", {}).get("embedding", {}).get("pooling", "cls")),
                "normalization": "L2"}
    reusable = {}
    if base is not None:
        if (not revision or base.manifest.get("embedding_status") != "complete"
                or base.manifest.get("splitter_version", SPLITTER_VERSION) != SPLITTER_VERSION
                or any(base.manifest.get(k) != v for k, v in identity.items())):
            raise ValueError("BASE_EMBEDDING_IDENTITY_MISMATCH")
        inventory = chunk_inventory or {}
        for i, unit in enumerate(base.units):
            if all(key in inventory and inventory[key] == base.manifest.get("chunk_inventory", {}).get(key) for key in unit.chunk_ids):
                reusable[unit.unit_id] = (unit, base.embeddings[i].tolist())
    vectors, dimension = [], None
    for start in range(0, len(units), batch_size):
        batch = units[start:start + batch_size]
        keys = [_cache_key(identity, u.text) for u in batch]
        rows, misses = [], []
        for i, (key, unit) in enumerate(zip(keys, batch)):
            old = reusable.get(unit.unit_id)
            entry = _CACHE.get(key) if USE_CACHE and revision else None
            row = old[1] if old and old[0] == unit else None
            if row is None and isinstance(entry, dict) and entry.get("identity") == identity and entry.get("text_sha256") == sha256(unit.text.encode()).hexdigest():
                row = entry.get("v")
            rows.append(row)
            if row is None:
                misses.append(i)
        fresh = _embed_batch(client, [batch[i].text for i in misses]) if misses else []
        entries = []
        for i, row in zip(misses, fresh):
            rows[i] = row
            entries.append({"k": keys[i], "v": row, "identity": identity,
                            "text_sha256": sha256(batch[i].text.encode()).hexdigest(), "dimension": len(row) if isinstance(row, list) else 0})
        if not isinstance(rows, list) or len(rows) != len(batch):
            raise ValueError("EMBEDDING_BATCH_COUNT_MISMATCH")
        for row in rows:
            if (not isinstance(row, list) or not row or any(type(v) not in (int, float) for v in row)
                    or (dimension is not None and len(row) != dimension)):
                raise ValueError("INVALID_EMBEDDING_ROW")
            if not np.isfinite(row).all() or np.linalg.norm(row) == 0:
                raise ValueError("INVALID_EMBEDDING_ROW")
            dimension = len(row)
        if USE_CACHE and revision and entries:
            _append_cache(entries)
            _CACHE.update({entry["k"]: entry for entry in entries})
        vectors.extend(rows)
        print(json.dumps({"embedded": len(vectors), "total": len(units)}), flush=True)
    dimension = dimension or (base.embeddings.shape[1] if base is not None else 0)
    matrix = normalize_embeddings(vectors, len(units)) if units else np.empty((0, dimension), dtype=np.float32)
    return matrix, {**identity, "embedding_batch_size": batch_size, "splitter_version": SPLITTER_VERSION}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "evals/corpus/served-chunks.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "data/rag_v2_index")
    parser.add_argument("--embed", action="store_true", help="Call local /info and /embed; without this, save an explicitly pending (N,0) matrix")
    parser.add_argument("--base", type=Path, help="Reuse unchanged chunk vectors from this validated snapshot")
    parser.add_argument("--batch-size", type=int, default=20, choices=range(1, 21))
    args = parser.parse_args(argv)
    # Preflight all output paths before any model request or file creation.
    from campus247.rag_v2.adapters.index_store import FILES, _directory
    output = _directory(args.output)
    if any((output / name).exists() or (output / name).is_symlink() for name in FILES):
        parser.error("INDEX_ALREADY_EXISTS: choose a fresh --output; existing evidence is preserved")
    payload = args.corpus.read_bytes()
    source_rows = [json.loads(line) for line in payload.decode("utf-8").splitlines() if line.strip()]
    # Reuse the exporter's validation/family assignment, not a duplicate classifier.
    chunks = [normalize_row(row) for row in source_rows]
    if len({r["chunk_id"] for r in chunks}) != len(chunks):
        raise ValueError("DUPLICATE_CORPUS_CHUNK")
    units = build_units(chunks)
    issues = check_units(chunks, units)
    if issues:
        raise ValueError(f"UNIT_CHECK_FAILED: {Counter(i.code for i in issues)}")
    facts = extract_facts(units)
    manifest = {"corpus_sha256": sha256(payload).hexdigest(), "chunk_count": len(chunks),
                "coverage_by_family": coverage_stats(chunks, units),
                "facts_by_kind": dict(Counter(f.kind for f in facts)),
                "embedding_model": None, "release_id": None, "generation": None,
                "chunk_inventory": chunk_inventory(chunks), "chunk_gaps": inventory_gaps(chunks, units),
                "splitter_version": SPLITTER_VERSION}
    source_manifest = args.corpus.with_name("manifest.json")
    if source_manifest.exists():
        exported = json.loads(source_manifest.read_text(encoding="utf-8"))
        if exported.get("sha256") != manifest["corpus_sha256"]:
            raise ValueError("CORPUS_MANIFEST_HASH_MISMATCH")
        snapshot = exported.get("snapshot", {})
        manifest.update({k: snapshot.get(k) for k in ("release_id", "generation", "policy_generation")})
    matrix = np.empty((len(units), 0), dtype=np.float32)
    base = read_index(args.base) if args.base else None
    if args.base and not args.embed:
        parser.error("--base requires --embed")
    if args.embed:
        globals()["USE_CACHE"] = True
        matrix, model_metadata = embed_units(units, batch_size=args.batch_size, base=base,
            chunk_inventory=manifest["chunk_inventory"])
        if not model_metadata.get("embedding_revision"):
            raise ValueError("EMBEDDING_REVISION_REQUIRED")
        manifest.update(model_metadata)
    write_index(output, units, facts, matrix, manifest)
    saved = read_index(output)
    print(json.dumps(saved.manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except httpx.HTTPStatusError as error:
        print(f"INDEX_BUILD_FAILED: HTTP_STATUS_{error.response.status_code}", file=sys.stderr)
        raise SystemExit(1) from None
    except (httpx.HTTPError, OSError, ValueError) as error:
        # No headers, request text, environment or credentials enter diagnostics.
        print(f"INDEX_BUILD_FAILED: {type(error).__name__}", file=sys.stderr)
        raise SystemExit(1) from None
