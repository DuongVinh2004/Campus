"""L-14: quét hằng số RRF k bằng đường đóng gói thật của RagV2Service (probe --authorized, mọi đơn vị được phép).

Tiêu chí: mọi required_fact có trong ngữ cảnh đưa cho mô hình. Vector thật từ 18081 (local, miễn phí); không gọi DeepSeek.
.venv/Scripts/python.exe -B evals/results/audit-opus-20261101/l14_sweep.py 60,30,20,10
"""
import asyncio
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

sys.stdout.reconfigure(encoding="utf-8")


def load_cases():
    dev = [json.loads(l) for l in (ROOT / "evals/datasets/rag-v2/cases.jsonl").read_text(encoding="utf-8").splitlines()]
    dev = [c for c in dev if c["split"] == "dev" and c["expected"] == "answer"]
    audit = [json.loads(l) for l in (HERE / "cases.jsonl").read_text(encoding="utf-8").splitlines()]
    return dev + [c for c in audit if c["expected"] == "answer"]


async def main():
    ks = [int(k) for k in sys.argv[1].split(",")]
    base = probe.MemoryIndex(ROOT / "data/rag_v2_index/embedded2", probe.embed)
    corpus = {json.loads(l)["chunk_id"]: json.loads(l) for l in
              (ROOT / "evals/corpus/served-chunks.jsonl").read_text(encoding="utf-8").splitlines()}
    index = probe.authorized_index(base, corpus, allowed=set(base.all_ids()))
    cases = load_cases()
    out = {"cases": len(cases), "by_k": {}, "per_case": {}}
    for k in ks:
        hybrid.RRF_K = k
        ok_ids = []
        for case in cases:
            context = await probe.runtime_context(index, case["question"])
            blob = " ".join(s["text"] for s in context["units"])
            facts = case["required_facts"]
            if facts and all(fact_matches(f, blob) for f in facts):
                ok_ids.append(case["case_id"])
        out["by_k"][k] = {"facts_in_context": len(ok_ids),
                          "dev": sum(1 for c in ok_ids if not c.startswith("AU-")),
                          "audit": sum(1 for c in ok_ids if c.startswith("AU-"))}
        out["per_case"][k] = ok_ids
        print(k, out["by_k"][k], flush=True)
        (HERE / "l14-sweep.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


asyncio.run(main())
