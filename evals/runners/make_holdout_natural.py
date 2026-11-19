"""Build the sealed hold-out for the natural-question eval from the pre-existing `holdout` split of cases.jsonl.

The split is made by hash of group_id (see cases.manifest.json), so the variants of one question never straddle
dev and hold-out. Groups that were used as seeds for the tuned natural set are removed, so no question here was
seen while the guards, analyzer or verifier were tuned. Output has the same shape as natural-cases (``style`` is the
phrasing variant: form / no_diacritics / keyword / slang).

  python evals/runners/make_holdout_natural.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "evals/datasets/rag-v2"
rows = [json.loads(l) for l in (D / "cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
natural = [json.loads(l) for l in (D / "natural-cases-20261114.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
seed_ids = {c["seed_id"] for c in natural if c.get("seed_id")}
seed_groups = {r["group_id"] for r in rows if r["case_id"] in seed_ids}
out = []
for r in rows:
    if r["split"] != "holdout" or r["group_id"] in seed_groups:
        continue
    out.append({"case_id": "HO-" + r["case_id"] + "-" + r["variant"], "group_id": r["group_id"], "style": r["variant"],
                "family": r["family"], "expected": r["expected"], "question": r["question"],
                "required_facts": r.get("required_facts", []), "forbidden_facts": r.get("forbidden_facts", []),
                "gold": r.get("gold", [])})
(D / "holdout-natural-20261114.jsonl").write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in out) + "\n", encoding="utf-8")
import collections
print(len(out), "cases;", len({o["group_id"] for o in out}), "groups;", dict(collections.Counter(o["expected"] for o in out)),
      dict(collections.Counter(o["style"] for o in out)))
