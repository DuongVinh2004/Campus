"""Check complete A/B sweeps against the immutable W12 baseline."""
import json
from hashlib import sha256

from w14_validate import HERE, PROTECTED, ROOT, write_fresh


def main():
    baseline = json.loads((HERE / "w12-embedded2-sweep.json").read_text(encoding="utf-8"))
    baseline_ok = set(baseline["per_case"]["60"])
    baseline_ids = {row["case_id"] for row in baseline["contexts"]["60"]}
    assert len(baseline_ids) == baseline["cases"] == 477
    assert baseline["by_k"]["60"] == {"facts_in_context": 281, "dev": 262, "audit": 19}
    result = {"baseline": baseline["by_k"]["60"], "cases": 477, "runs": {}}
    for label, flag in (("A", False), ("B", True)):
        path = HERE / f"w14-embedded3-{label}-sweep.json"
        run = json.loads(path.read_text(encoding="utf-8"))
        contexts = run["contexts"]["60"]
        assert len(contexts) == run["cases"] == 477
        assert {row["case_id"] for row in contexts} == baseline_ids
        assert run["focused_lexical"] is flag and run["provider_calls"] == 0
        ok = set(run["per_case"]["60"])
        assert ok == {row["case_id"] for row in contexts if row["facts_in_context"]}
        assert len(ok) == run["by_k"]["60"]["facts_in_context"]
        result["runs"][label] = {"summary": run["by_k"]["60"],
                                  "gained": sorted(ok - baseline_ok), "lost": sorted(baseline_ok - ok),
                                  "AU-A23": next(row for row in contexts if row["case_id"] == "AU-A23"),
                                  "sha256": sha256(path.read_bytes()).hexdigest()}
    b = result["runs"]["B"]
    result["adoptable"] = len(b["lost"]) <= len(b["gained"]) and b["AU-A23"]["line29_in_context"]
    result["protected_sha256"] = {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in PROTECTED}
    assert result["protected_sha256"] == PROTECTED
    write_fresh("w14-comparison.json", result)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
