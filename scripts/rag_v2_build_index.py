"""Build a fresh index. Add --embed for the local BGE-m3 server; never overwrite."""
from __future__ import annotations

import argparse
import json
import sys
import time
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
    read_index,
    write_index,
)
from campus247.rag_v2.facts.extract import extract_facts
from campus247.rag_v2.ingest.checks import check_units, coverage_stats
from campus247.rag_v2.ingest.units import build_units

from evals.runners.corpus_export import normalize_row


CACHE_PATH = ROOT / "data" / "rag_v2_index" / "embed-cache.jsonl"  # resume file: text sha256 -> vector
_CACHE: dict = {}
USE_CACHE = False  # the CLI turns the resume cache on; library callers and tests never touch it
if CACHE_PATH.exists():
    for _line in CACHE_PATH.read_text(encoding="utf-8").splitlines():
        try:
            _row = json.loads(_line)
            _CACHE[_row["k"]] = _row["v"]
        except (ValueError, KeyError):
            pass


def _embed_batch(client, texts):
    """The model server rejects a request over its token cap with 503; split and retry down to one text."""
    for attempt in range(8):
        response = client.post("/embed", json={"inputs": texts, "normalize": True, "truncate": False})
        if response.status_code == 200:
            rows = response.json()
            if not isinstance(rows, list) or len(rows) != len(texts):
                raise ValueError("EMBEDDING_BATCH_COUNT_MISMATCH")
            return rows
        if response.status_code != 503:
            response.raise_for_status()
        if len(texts) > 1:
            half = len(texts) // 2
            return _embed_batch(client, texts[:half]) + _embed_batch(client, texts[half:])
        time.sleep(2 + 3 * attempt)
    # A single text the server keeps refusing is over its token cap: embed a shorter prefix instead.
    if len(texts) == 1 and len(texts[0]) > 300:
        print(json.dumps({"embed_prefix_fallback": len(texts[0])}), flush=True)
        return _embed_batch(client, [texts[0][: max(300, int(len(texts[0]) * 0.6))]])
    response.raise_for_status()


def embed_units(units, *, batch_size=20, client=None):
    if not 1 <= batch_size <= 20:
        raise ValueError("BATCH_SIZE_MUST_BE_1_TO_20")
    if client is None:
        with httpx.Client(base_url="http://127.0.0.1:18081", timeout=120, trust_env=False, follow_redirects=False) as active:
            return embed_units(units, batch_size=batch_size, client=active)
    info_response = client.get("/info")
    info_response.raise_for_status()
    info = info_response.json()
    if (str(info.get("model_id", "")).casefold() != "baai/bge-m3"
            or set(info.get("model_type", {})) != {"embedding"}
            or info.get("auto_truncate") is not False):
        raise ValueError("LOCAL_BGE_M3_IDENTITY_REJECTED")
    vectors, dimension = [], None
    for start in range(0, len(units), batch_size):
        batch = units[start:start + batch_size]
        keys = [sha256(u.text.encode("utf-8")).hexdigest() for u in batch]
        rows = [_CACHE.get(k) if USE_CACHE else None for k in keys]
        if any(r is None for r in rows):
            rows = _embed_batch(client, [u.text for u in batch])
            if USE_CACHE:
                with CACHE_PATH.open("a", encoding="utf-8") as handle:
                    for k, row in zip(keys, rows):
                        _CACHE[k] = row
                        handle.write(json.dumps({"k": k, "v": row}) + "\n")
        if not isinstance(rows, list) or len(rows) != len(batch):
            raise ValueError("EMBEDDING_BATCH_COUNT_MISMATCH")
        for row in rows:
            if (not isinstance(row, list) or not row or any(type(v) not in (int, float) for v in row)
                    or (dimension is not None and len(row) != dimension)):
                raise ValueError("INVALID_EMBEDDING_ROW")
            dimension = len(row)
        vectors.extend(rows)
        print(json.dumps({"embedded": len(vectors), "total": len(units)}), flush=True)
    matrix = normalize_embeddings(vectors, len(units))
    return matrix, {"embedding_model": info["model_id"], "embedding_revision": info.get("model_sha"),
                    "embedding_batch_size": batch_size}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "evals/corpus/served-chunks.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "data/rag_v2_index")
    parser.add_argument("--embed", action="store_true", help="Call local /info and /embed; without this, save an explicitly pending (N,0) matrix")
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
                "embedding_model": None, "release_id": None, "generation": None}
    source_manifest = args.corpus.with_name("manifest.json")
    if source_manifest.exists():
        exported = json.loads(source_manifest.read_text(encoding="utf-8"))
        if exported.get("sha256") != manifest["corpus_sha256"]:
            raise ValueError("CORPUS_MANIFEST_HASH_MISMATCH")
        snapshot = exported.get("snapshot", {})
        manifest.update({k: snapshot.get(k) for k in ("release_id", "generation", "policy_generation")})
    matrix = np.empty((len(units), 0), dtype=np.float32)
    if args.embed:
        globals()["USE_CACHE"] = True
        matrix, model_metadata = embed_units(units, batch_size=args.batch_size)
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
