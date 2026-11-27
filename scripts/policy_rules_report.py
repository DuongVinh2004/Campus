"""Write evals/results/policy-rules-<date>/<rule>.json: vector counts, gold match, rule hash, quote check."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api" / "src"))
from campus247.application.policy_rules.service import PolicyRulesService  # noqa: E402
from campus247.domain.policy_rules.variables import load_vocabulary  # noqa: E402
from campus247.infrastructure.knowledge.rag_v2_units import RagV2Units  # noqa: E402
from campus247.infrastructure.repositories.sqlite_policy_rules import PolicyRulesStore  # noqa: E402

units = RagV2Units(ROOT / "data" / "rag_v2_index")
with tempfile.TemporaryDirectory() as tmp:
    svc = PolicyRulesService(PolicyRulesStore(Path(tmp) / "r.sqlite3"), load_vocabulary(ROOT / "config/policy/variables.toml"), units.text, units.release)
    result = svc.seed_from_directory(ROOT / "config/policy/rules", ROOT / "config/policy/gold")
    out = ROOT / "evals" / "results" / f"policy-rules-{date.today():%Y%m%d}"
    out.mkdir(parents=True, exist_ok=True)
    for rec in svc.store.current_records():
        vectors = svc.store.vectors(rec["rule_id"], rec["version"])
        by = {}
        for v in vectors:
            by[v["origin"]] = by.get(v["origin"], 0) + 1
        gold = svc.gold_report(vectors)
        (out / f"{rec['body']['topic']}.json").write_text(json.dumps({
            "topic": rec["body"]["topic"], "rule": {"rule_id": rec["rule_id"], "version": rec["version"], "content_sha256": rec["content_sha256"]},
            "release_id": units.release()["release_id"], "vectors_by_origin": by, "gold": gold,
            "evidence": "scenarios authored from the regulation wording by the same model that wrote the rules; source spans and quotes checked by code; engine checked against an independent two-valued oracle; not measured with real users"},
            ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"published": len(result["published"]), "failed": result["failed"]}), out)
