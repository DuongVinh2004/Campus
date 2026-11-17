"""L-14: hạng BM25 / vector / RRF của đơn vị gold cho từng ca (chỉ mục thật, vector thật từ 18081, không gọi DeepSeek).

.venv/Scripts/python.exe -B evals/results/audit-opus-20261101/l14_diagnose.py <cases.jsonl> [case_id ...]
"""
import asyncio
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services/api/src"))
spec = importlib.util.spec_from_file_location("probe", ROOT / "evals/runners/rag_v2_context_probe.py")
probe = importlib.util.module_from_spec(spec)
sys.modules["probe"] = probe
spec.loader.exec_module(probe)
from campus247.rag_v2.understanding.analyze import analyze  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")


async def main():
    index = probe.MemoryIndex(ROOT / "data/rag_v2_index/embedded2", probe.embed)
    allowed_out = Path(__file__).with_name("l14-allowed-all.json")
    if not allowed_out.exists():
        allowed_out.write_text(json.dumps(sorted(index.all_ids())), encoding="utf-8")
    cases = [json.loads(l) for l in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if l.strip()]
    wanted = set(sys.argv[2:])
    for case in cases:
        if wanted and case["case_id"] not in wanted:
            continue
        gold_chunks = {g["chunk_id"] for g in case.get("gold", [])}
        gold_units = {uid for uid in index.all_ids() if gold_chunks & set(index.get(uid).chunk_ids)}
        u = analyze(case["question"], ())
        allowed = set(index.all_ids())
        lex = [uid for uid, _ in index.lexical(u.search_query, 80, allowed=allowed)]
        vec = [uid for uid, _ in await index.vector(u.search_query, 80, allowed=allowed)]
        ranks = {}
        for branch, rows in enumerate((lex[:40], vec[:40])):
            for rank, uid in enumerate(rows, 1):
                ranks.setdefault(uid, [None, None])[branch] = rank
        fused = sorted(ranks, key=lambda uid: (-sum(1 / (60 + r) for r in ranks[uid] if r), uid))
        best = lambda rows: min((rows.index(g) + 1 for g in gold_units if g in rows), default=None)
        print(case["case_id"], "| q:", u.search_query[:60])
        print("  gold units", len(gold_units), "| lexical rank", best(lex), "| vector rank", best(vec),
              "| fused rank", best(fused), "of", len(fused))
        top = fused[:12]
        print("  fused top12 lex/vec ranks:", [tuple(ranks[x]) for x in top])


asyncio.run(main())
