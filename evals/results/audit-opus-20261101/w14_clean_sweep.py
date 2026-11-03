"""L-14: quét hằng số RRF k bằng đường đóng gói thật của RagV2Service (probe --authorized, mọi đơn vị được phép).

Tiêu chí: mọi required_fact có trong ngữ cảnh đưa cho mô hình. Vector thật từ 18081 (local, miễn phí); không gọi DeepSeek.
.venv/Scripts/python.exe -B evals/results/audit-opus-20261101/l14_sweep.py 60,30,20,10
"""
import asyncio
import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "services/api/src"))
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("probe", ROOT / "evals/runners/rag_v2_context_probe.py")
probe = importlib.util.module_from_spec(spec)
sys.modules["probe"] = probe
spec.loader.exec_module(probe)
from campus247.rag_v2.retrieval import hybrid  # noqa: E402
from evals.runners.rag_v2_eval import fact_matches  # noqa: E402

# --- experiment W14: drop interrogative filler words from the LEXICAL query only (vector query unchanged)
import re as _re
from campus247.rag_v2.understanding.normalize import fold as _fold
_FILLER = {"do", "nao", "gi", "la", "thi", "vay", "nhe", "sao", "the", "em", "minh", "toi", "hoi", "xin", "bao", "nhieu"}


def _clean(query):
    words = _re.findall(r"\w+", query.lower())
    kept = [w for w in words if _fold(w) not in _FILLER]
    return " ".join(kept) if len(kept) >= 2 else query


_orig_lexical = probe.MemoryIndex.lexical


def _lexical(self, query, limit, *, allowed=None):
    return _orig_lexical(self, _clean(query), limit, allowed=allowed)


probe.MemoryIndex.lexical = _lexical

sys.stdout.reconfigure(encoding="utf-8")


def load_cases():
    dev = [json.loads(l) for l in (ROOT / "evals/datasets/rag-v2/cases.jsonl").read_text(encoding="utf-8").splitlines()]
    dev = [c for c in dev if c["split"] == "dev" and c["expected"] == "answer"]
    audit = [json.loads(l) for l in (HERE / "cases.jsonl").read_text(encoding="utf-8").splitlines()]
    return dev + [c for c in audit if c["expected"] == "answer"]


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ks", nargs="?", default=str(hybrid.RRF_K))
    parser.add_argument("--index", type=Path, default=ROOT / "data/rag_v2_index/embedded2")
    parser.add_argument("--output", type=Path, default=HERE / "w12-sweep.json")
    args = parser.parse_args()
    index_dir = args.index.resolve()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT) or output.exists() or args.output.is_symlink():
        parser.error("--output must be a fresh file inside the workspace")
    ks = [int(k) for k in args.ks.split(",")]
    base = probe.MemoryIndex(index_dir, probe.embed)
    corpus = {json.loads(l)["chunk_id"]: json.loads(l) for l in
              (ROOT / "evals/corpus/served-chunks.jsonl").read_text(encoding="utf-8").splitlines()}
    index = probe.authorized_index(base, corpus, allowed=set(base.all_ids()))
    cases = load_cases()
    out = {"cases": len(cases), "index": str(index_dir),
           "splitter_version": base.manifest.get("splitter_version"),
           "lexical_pin": hybrid.LEXICAL_PIN, "provider_calls": 0,
           "by_k": {}, "per_case": {}, "contexts": {}}
    # Reserve a new evidence file; only this run's checkpoints may update it.
    with output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(out, ensure_ascii=False, indent=1))
    for k in ks:
        hybrid.RRF_K = k
        ok_ids = []
        out["contexts"][k] = []
        for position, case in enumerate(cases, 1):
            context = await probe.runtime_context(index, case["question"])
            blob = " ".join(s["text"] for s in context["units"])
            facts = case["required_facts"]
            if facts and all(fact_matches(f, blob) for f in facts):
                ok_ids.append(case["case_id"])
            out["contexts"][k].append({"case_id": case["case_id"],
                "facts_in_context": case["case_id"] in ok_ids,
                "chunk_ids": context["chunk_ids"], "context_sha256": context["context_sha256"]})
            print(f"{index_dir.name} k={k} {position}/{len(cases)} {case['case_id']} facts={case['case_id'] in ok_ids}", flush=True)
            output.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        out["by_k"][k] = {"facts_in_context": len(ok_ids),
                          "dev": sum(1 for c in ok_ids if not c.startswith("AU-")),
                          "audit": sum(1 for c in ok_ids if c.startswith("AU-"))}
        out["per_case"][k] = ok_ids
        print(k, out["by_k"][k], flush=True)
        output.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


asyncio.run(main())
