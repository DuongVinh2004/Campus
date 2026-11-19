"""Export the local serving release without writing to PostgreSQL.

Run: .venv/Scripts/python.exe -B evals/runners/corpus_export.py
Existing corpus files are never replaced. Only public knowledge fields are
selected; the exporter does not read conversations, users or runtime credentials
other than the local connection record consumed by knowledge_platform.connection.
"""
from __future__ import annotations

import asyncio
import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "evals/corpus"
EXPECTED_COUNTS = {"chunk_count": 2515, "version_count": 151, "document_count": 123}
FIELDS = ("chunk_id", "document_id", "version_id", "doc_title", "doc_family",
          "section_label", "page", "text")


def document_family(title: str) -> str:
    """Deterministic title label for case sampling, not legal applicability.

    The DB has no corpus-category column. Keep unknown titles as `khac` rather
    than inventing a category; the original title remains available to authors.
    """
    folded = "".join(c for c in unicodedata.normalize("NFD", title.casefold())
                     if unicodedata.category(c) != "Mn").replace("đ", "d")
    if re.search(r"\b(chuong trinh dao tao|ctdt|curriculum)\b", folded):
        return "ctdt"
    if re.search(r"\b(so tay|handbook)\b", folded):
        return "so_tay"
    if re.search(r"\b(hoc phi|tuition)\b", folded):
        return "hoc_phi"
    if re.search(r"\b(quy che|quy dinh|regulation)\b", folded):
        return "quy_che"
    if re.search(r"\b(thong bao|notice|announcement)\b", folded):
        return "thong_bao"
    return "khac"


def normalize_row(row) -> dict:
    """Whitelist fields, stringify DB UUIDs and retain source text verbatim."""
    result = {}
    for field in ("chunk_id", "document_id", "version_id"):
        value = row[field]
        if value is None or not str(value).strip():
            raise ValueError("MISSING_CORPUS_ID")
        result[field] = str(value)
    title, text = row["doc_title"], row["text"]
    if not isinstance(title, str) or not title.strip():
        raise ValueError("EMPTY_DOCUMENT_TITLE")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("EMPTY_CHUNK")
    section, page = row["section_label"], row["page"]
    if section is not None and not isinstance(section, str):
        raise ValueError("INVALID_SECTION_LABEL")
    if page is not None and (type(page) is not int or page < 1):
        raise ValueError("INVALID_PAGE")
    result.update(doc_title=title, doc_family=document_family(title),
                  section_label=section, page=page, text=text)
    return result


def serialize_corpus(rows) -> tuple[bytes, dict]:
    """Validate before opening files and hash the exact UTF-8 JSONL bytes."""
    records = [normalize_row(row) for row in rows]
    if not records:
        raise ValueError("EMPTY_CORPUS")
    ids = [row["chunk_id"] for row in records]
    if len(set(ids)) != len(ids):
        raise ValueError("DUPLICATE_CHUNK_ID")
    records.sort(key=lambda row: row["chunk_id"])
    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                      for row in records).encode("utf-8")
    counts = {"chunk_count": len(records),
              "version_count": len({row["version_id"] for row in records}),
              "document_count": len({row["document_id"] for row in records})}
    return payload, {"file": "served-chunks.jsonl", **counts,
                     "sha256": hashlib.sha256(payload).hexdigest(),
                     "expected_counts": EXPECTED_COUNTS,
                     "matches_expected_counts": counts == EXPECTED_COUNTS,
                     "doc_family_basis": "title keywords; unclassified titles use khac"}


def corpus_query(relation: str) -> str:
    """Reuse runtime joins/eligibility, with the union of its source scopes.

    No question/actor is involved in a corpus inventory: intersect each source's
    scope arrays with themselves. Preserve campus, effective time, tenant,
    review, revocation, seal, index and approval checks. Edition selection is
    question-dependent, so all eligible members (including additional editions
    in the sealed profile) are retained for later case generation.
    """
    from campus247.infrastructure.knowledge.runtime import served_corpus_query
    return served_corpus_query(relation)


async def read_served_rows(conn, *, tenant: str, relation: str):
    """All reads share one database-enforced, repeatable read-only snapshot."""
    async with conn.transaction(isolation="repeatable_read", readonly=True):
        if await conn.fetchval("SHOW transaction_read_only") != "on":
            raise RuntimeError("READ_ONLY_TRANSACTION_REQUIRED")
        pointer = await conn.fetchrow("""SELECT release_id,generation,policy_generation
            FROM knowledge_release_pointer WHERE tenant_id=$1 AND campus_id=$2""", tenant, "HUCE")
        if not pointer or not pointer["release_id"]:
            raise ValueError("NO_SERVING_RELEASE")
        as_of = await conn.fetchval("SELECT CURRENT_TIMESTAMP")
        rows = await conn.fetch(corpus_query(relation), pointer["release_id"], tenant, as_of, "HUCE")
        snapshot = {"release_id": str(pointer["release_id"]),
                    "generation": pointer["generation"],
                    "policy_generation": pointer["policy_generation"],
                    "as_of": as_of.isoformat(), "transaction_read_only": True,
                    "selection": "runtime RELATION; union of source scopes; all eligible release editions"}
    return rows, snapshot


def export_paths(output_dir=None) -> tuple[Path, Path]:
    """Canonical workspace-only destinations, with exclusive creation."""
    candidate = Path(output_dir) if output_dir is not None else CORPUS
    if ".." in candidate.parts or any(c in str(candidate) for c in "*?{}"):
        raise ValueError("AMBIGUOUS_CORPUS_PATH")
    directory = candidate.resolve()
    if not directory.is_relative_to(ROOT.resolve()) or directory == ROOT.resolve():
        raise ValueError("CORPUS_OUTSIDE_WORKSPACE")
    paths = tuple(directory / name for name in ("served-chunks.jsonl", "manifest.json"))
    if any(path.exists() or path.is_symlink() for path in paths):
        raise FileExistsError("CORPUS_ALREADY_EXISTS")
    return paths


def write_export(rows, snapshot: dict, *, output_dir=None) -> dict:
    payload, manifest = serialize_corpus(rows)
    # Only known non-sensitive snapshot metadata can enter the manifest.
    manifest["snapshot"] = {key: snapshot[key] for key in (
        "release_id", "generation", "policy_generation", "as_of",
        "transaction_read_only", "selection")}
    metadata = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    corpus, destination = export_paths(output_dir) if output_dir is not None else export_paths()
    corpus.parent.mkdir(parents=True, exist_ok=True)
    export_paths(output_dir) if output_dir is not None else export_paths()
    # Keep any partial files as evidence on I/O failure; never erase user data.
    with corpus.open("xb") as stream:
        stream.write(payload)
    with destination.open("xb") as stream:
        stream.write(metadata)
    return manifest


async def run(*, output_dir=None) -> dict:
    export_paths(output_dir)  # Refuse existing outputs before connecting.
    sys.path.insert(0, str(ROOT / "scripts"))
    from knowledge_platform import TENANT, connection
    import asyncpg
    from campus247.infrastructure.knowledge.runtime import RELATION

    conn = await asyncpg.connect(**connection(), timeout=5, command_timeout=30)
    try:
        rows, snapshot = await read_served_rows(conn, tenant=TENANT, relation=RELATION)
    finally:
        await conn.close()
    return write_export(rows, snapshot, output_dir=output_dir)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="Fresh immutable workspace corpus directory")
    args = parser.parse_args(argv if argv is not None else [])
    try:
        manifest = asyncio.run(run(output_dir=args.output_dir) if args.output_dir is not None else run())
    except Exception as error:  # Never emit exception text/DSNs/source content.
        print("CORPUS_EXPORT_FAILED: " + type(error).__name__, file=sys.stderr)
        return 1
    print(json.dumps({key: manifest[key] for key in (
        "chunk_count", "version_count", "document_count", "sha256", "matches_expected_counts")}))
    if not manifest["matches_expected_counts"]:
        print("CORPUS_HISTORICAL_REFERENCE: counts differ from historical baseline", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
