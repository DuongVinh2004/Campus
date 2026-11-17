"""Read-only corpus/index checks; create fresh W14 evidence inside workspace."""
import json
import sys
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "services/api/src"), str(ROOT)]

from campus247.rag_v2.adapters.index_store import read_index
from campus247.rag_v2.ingest import units as splitter
from campus247.rag_v2.ingest.checks import check_units, coverage_stats
from campus247.rag_v2.ingest.tables import flat_list_rows
from evals.runners.corpus_export import normalize_row

PROTECTED = {
    "evals/corpus/served-chunks.jsonl": "ddeca7cb59d307be519dfca5ae7fa8e061cacd306e6d1af25718a1f8fc042524",
    "evals/results/audit-opus-20261101/w12_sweep.py": "f136d4e42e6de63a63e4b24672a48e5ab2cc13b021325d452e8f4fa52e202b3c",
    "evals/results/audit-opus-20261101/w12-embedded2-sweep.json": "ca28e3ec0f48ad5e642550dc5eb9d2aff5acc0940dbef010e4e468bbbd6cf78a",
    "evals/datasets/rag-v2/cases.jsonl": "0b6ffbac00ccba1e8326f1d7437ff08c1a06c0658fdc15c17b765db6dc0d9cbf",
    "evals/results/audit-opus-20261101/cases.jsonl": "cc63e385f7a5f565c1ac5eb50ad5f0973f74c4e8d04866ec2d99091c216f2bbe",
    "data/rag_v2_index/embedded2/embeddings.npy": "ba14882995f58dce585556f14af1f3e1fef6e0f3e0ab106746a810694eb59dc8",
    "data/rag_v2_index/embedded2/facts.jsonl": "a92211d63f1fc0215ad67fa09da9198e3d5a31f6635b50de45366f54abde0241",
    "data/rag_v2_index/embedded2/manifest.json": "3215451df0b8db581b56bd96b2650bc857f7c70399e5f91006237477009e82a0",
    "data/rag_v2_index/embedded2/units.jsonl": "2b2b883df15e484d5214a0f911bb283fe9e7b28ae23036bc626c13911701beae",
}


def write_fresh(name, value):
    path = HERE / name
    assert path.resolve().is_relative_to(ROOT) and not path.exists()
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)


def validate():
    hashes = {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in PROTECTED}
    assert hashes == PROTECTED
    chunks = [normalize_row(json.loads(line)) for line in
              (ROOT / "evals/corpus/served-chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    snapshot = read_index(ROOT / "data/rag_v2_index/embedded3")
    current = snapshot.units
    assert check_units(chunks, current) == []
    detector = splitter.flat_list_rows
    try:
        splitter.flat_list_rows = lambda _: {}
        old = splitter.build_units(chunks)
    finally:
        splitter.flat_list_rows = detector
    stored_old = [json.loads(line) for line in
                  (ROOT / "data/rag_v2_index/embedded2/units.jsonl").read_text(encoding="utf-8").splitlines()]
    # JSON conversion normalizes tuple/list representation only.
    assert json.loads(json.dumps([asdict(u) for u in old])) == stored_old
    affected = {row["chunk_id"] for row in chunks if flat_list_rows(row["text"])}
    untouched_old = [u for u in old if not affected.intersection(u.chunk_ids)]
    untouched_new = [u for u in current if not affected.intersection(u.chunk_ids)]
    assert untouched_old == untouched_new
    # Compare every pipe-containing chunk against the detector-disabled splitter.
    pipes = [row for row in chunks if "|" in row["text"] and row["chunk_id"] not in affected]
    assert pipes
    old_map, new_map = {u.unit_id: u for u in old}, {u.unit_id: u for u in current}
    assert sha256((ROOT / "data/rag_v2_index/embedded3/facts.jsonl").read_bytes()).hexdigest() == PROTECTED["data/rag_v2_index/embedded2/facts.jsonl"]
    result = {
        "protected_sha256": hashes, "protected_unchanged": True,
        "baseline_units_reproduced_exactly": True,
        "chunk_count": len(chunks), "before_units": len(old), "after_units": len(current),
        "before_kinds": dict(Counter(u.kind for u in old)),
        "after_kinds": dict(Counter(u.kind for u in current)),
        "unaffected_units_identical": len(untouched_old), "unaffected_pipe_chunks": len(pipes),
        "affected_chunks": [{"chunk_id": row["chunk_id"], "page": row.get("page"),
                             "rows": len(flat_list_rows(row["text"]))}
                            for row in chunks if row["chunk_id"] in affected],
        "new_ids": sorted(new_map.keys() - old_map.keys()),
        "absent_old_ids_in_new_snapshot": sorted(old_map.keys() - new_map.keys()),
        "changed_common_ids": sorted(uid for uid in old_map.keys() & new_map.keys()
                                     if old_map[uid] != new_map[uid]),
        "checks": [], "coverage": coverage_stats(chunks, current),
        "facts_identical": True,
        "manifest": {key: snapshot.manifest.get(key) for key in (
            "unit_count", "fact_count", "splitter_version", "embedding_status", "embedding_dimension",
            "embedding_model", "embedding_revision", "embedding_batch_size", "binding_sha256")},
    }
    write_fresh("w14-unit-analysis.json", result)
    print(json.dumps({key: result[key] for key in ("before_units", "after_units", "unaffected_units_identical", "manifest")}))


if __name__ == "__main__":
    validate()
