"""L-30: mô phỏng mất dịch vụ nhúng (18081) trong tiến trình, không tắt dịch vụ dùng chung.

Vector adapter ném ConnectionError; so ngữ cảnh gửi mô hình với lượt bình thường trên cùng ca.
.venv/Scripts/python.exe -B evals/results/audit-opus-20261101/outage_sim.py
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
from evals.runners.rag_v2_eval import fact_matches  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")


async def down(text):
    raise ConnectionError("embedding service unavailable (simulated)")


async def main():
    dev = [json.loads(l) for l in (ROOT / "evals/datasets/rag-v2/cases.jsonl").read_text(encoding="utf-8").splitlines()]
    cases = [c for c in dev if c["split"] == "dev" and c["expected"] == "answer"][:60]
    corpus = {json.loads(l)["chunk_id"]: json.loads(l) for l in
              (ROOT / "evals/corpus/served-chunks.jsonl").read_text(encoding="utf-8").splitlines()}
    result = {}
    for name, embedder in (("normal", probe.embed), ("embedding_down", down)):
        base = probe.MemoryIndex(ROOT / "data/rag_v2_index/embedded2", embedder)
        index = probe.authorized_index(base, corpus, allowed=set(base.all_ids()))
        ok, empty = 0, 0
        for case in cases:
            ctx = await probe.runtime_context(index, case["question"])
            blob = " ".join(s["text"] for s in ctx["units"])
            empty += not ctx["units"]
            ok += bool(case["required_facts"]) and all(fact_matches(f, blob) for f in case["required_facts"])
        result[name] = {"cases": len(cases), "facts_in_context": ok, "empty_context": empty}
        print(name, result[name], flush=True)
    (HERE / "outage-sim.json").write_text(json.dumps(result, indent=1), encoding="utf-8")


asyncio.run(main())
