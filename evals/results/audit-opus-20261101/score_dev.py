"""Chấm một lượt audit_run trên tập dev136 bằng bộ chấm chung (rag_v2_scoring.classify) và so hai lượt.

.venv/Scripts/python.exe -B evals/results/audit-opus-20261101/score_dev.py dev136-before.json [dev136-after.json]
"""
import collections
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location("s", ROOT / "evals/runners/rag_v2_scoring.py")
scoring = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scoring)
sys.stdout.reconfigure(encoding="utf-8")
CASES = {json.loads(l)["case_id"]: json.loads(l) for l in
         (ROOT / "evals/results/rag-v2-audit-20261031/e2e/_dev136.jsonl").read_text(encoding="utf-8").splitlines()}


def classes(name):
    data = json.loads((HERE / name).read_text(encoding="utf-8"))
    out = {}
    for r in data["records"]:
        final = r.get("final") or {}
        row = {"outcome_class": r["outcome_class"], "answer_text": final.get("content", ""), "error": r.get("error"),
               "http_status": r.get("http_status"), "final_event": bool(final)}
        out[r["case_id"]] = scoring.classify(CASES[r["case_id"]], row)
    return out, data.get("paid_calls")


runs = [classes(n) for n in sys.argv[1:]]
for name, (cls, paid) in zip(sys.argv[1:], runs):
    print(name, dict(collections.Counter(cls.values())), "paid", paid)
if len(runs) == 2:
    a, b = runs[0][0], runs[1][0]
    changed = sorted((cid, a[cid], b[cid]) for cid in a if cid in b and a[cid] != b[cid])
    print("changed", len(changed))
    for row in changed:
        print("  ", *row)
