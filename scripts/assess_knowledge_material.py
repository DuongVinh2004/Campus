"""Re-score immutable receipts without model calls; keep old verdicts untouched."""
import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from knowledge_platform import ROOT, checked_path, retain

spec = importlib.util.spec_from_file_location("knowledge_claims", ROOT / "evals/runners/knowledge_claims.py")
claims = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = claims
spec.loader.exec_module(claims)


def source_envelope(case):
    final = case.get("final") or {}
    if final.get("status") != "answered":
        return {"name": case["name"], "status": final.get("status"), "material_checked": False,
                "answered_correctly": False, "reason": "No independent expected disposition in envelope diagnostic"}
    bodies = [s["body"] for s in case.get("sources", []) if s.get("status") == 200]
    valid = bool(bodies) and all(hashlib.sha256(b["content_text"].encode()).hexdigest() == b["citation"]["evidence_sha256"] for b in bodies)
    if not valid:
        return {"name": case["name"], "status": final.get("status"), "material_checked": False, "passed": False, "failures": ["source_envelope_missing_or_corrupt"]}
    gold = claims.Expectation("answered", "\n".join(b["content_text"] for b in bodies), witness_binding={"source_hashes": [b["citation"]["evidence_sha256"] for b in bodies]})
    return {"name": case["name"], "material_checked": True, **claims.assess_material(final, gold)}


def independent_rows(receipt, gold_file):
    gold = json.loads(gold_file.read_text(encoding="utf-8"))
    witness_file = checked_path(ROOT / gold["witness_file"], ROOT)
    raw = witness_file.read_bytes()
    if hashlib.sha256(raw).hexdigest() != gold["witness_file_sha256"]:
        raise ValueError("Frozen witness changed; do not update expected hashes to make evaluation pass")
    witness = json.loads(raw)
    for page in gold.get("image_witnesses",[]):
        image=checked_path(ROOT / page["image"],ROOT)
        if hashlib.sha256(image.read_bytes()).hexdigest()!=page["image_sha256"]:
            raise ValueError("Independent image witness changed")
    blocks = {b["block_id"]: b for b in witness["extracted"]["blocks"]}
    actual = {c["name"]: c for c in receipt["cases"]}
    if len(actual) != len(receipt["cases"]) or set(actual) != {c["name"] for c in gold["cases"]}:
        raise ValueError("Exactly one complete independent shard receipt is required")
    rows = []
    for expected in gold["cases"]:
        case = actual[expected["name"]]
        if case["question"] != expected["question"]:
            raise ValueError("Question differs from the frozen independent shard")
        block = blocks.get(expected.get("block_id"))
        expectation = claims.Expectation(expected["status"], block["text"] if block else "",
            required_terms=tuple(expected.get("required_terms", [])),
            required_conditions=tuple(tuple(g) for g in expected.get("required_conditions", [])),
            forbidden_terms=tuple(expected.get("forbidden_terms", [])),
            witness_binding={"source_id": gold["source_id"], "witness_sha256": gold["witness_file_sha256"], "block_id": expected.get("block_id")})
        result = claims.assess_material(case.get("final") or {}, expectation)
        if case.get("http_status") != 200:
            result["failures"].append("http")
        if expected["status"] == "answered":
            envelope = source_envelope(case)
            sources = case.get("sources", [])
            if not envelope.get("passed") or any(s["body"]["citation"]["source_id"] != gold["source_id"] for s in sources):
                result["failures"].append("source_envelope_binding")
            pages=expected.get("witness_pages",[block["page"]])
            if not all(any(s.get("status")==200 and isinstance(s["body"]["citation"]["locator"].get("page_start"),int)
                and s["body"]["citation"]["locator"]["page_start"]<=page<=s["body"]["citation"]["locator"].get("page_end",s["body"]["citation"]["locator"]["page_start"])
                for s in sources) for page in pages):
                result["failures"].append("source_page_binding")
        result["passed"] = not result["failures"]
        result["answered_correctly"] = result["passed"] and expected["status"] == "answered"
        result["correct_abstention"] = result["passed"] and expected["status"] == "abstained"
        result["correct_clarification"] = result["passed"] and expected["status"] == "clarification_needed"
        rows.append({"name": case["name"], "material_checked": True, **result})
    return rows, gold


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--known-counterexample", action="store_true")
    parser.add_argument("--gold", type=Path)
    args = parser.parse_args()
    source, target = checked_path(args.receipt.absolute(), ROOT), checked_path(args.output.absolute(), ROOT)
    if source == target or target.exists():
        raise ValueError("A new exact output is required; historical receipts stay immutable")
    raw = source.read_bytes()
    receipt = json.loads(raw)
    rows = [source_envelope(c) for c in receipt["cases"]]
    gold = None
    if args.gold:
        rows, gold = independent_rows(receipt, checked_path(args.gold.absolute(), ROOT))
    result = {"at": datetime.now(UTC), "receipt": str(source.relative_to(ROOT)), "receipt_sha256": hashlib.sha256(raw).hexdigest(),
        "method": "source-envelope material diagnostic v1; not an independent semantic correctness score",
        "count": len(rows), "material_checked": sum(r["material_checked"] for r in rows),
        "material_failures": sum(r.get("passed") is False for r in rows), "verdicts": rows,
        "independent_quality_campaign": False, "new_model_calls": 0, "historical_verdict_changed": False}
    if gold:
        result.update(gold_revision=gold["revision"], gold_limitations=gold["limitations"],
            answered_correctly=sum(r.get("answered_correctly", False) for r in rows),
            correct_abstentions=sum(r.get("correct_abstention", False) for r in rows))
    if args.known_counterexample:
        case = copy.deepcopy(next(c for c in receipt["cases"] if c["name"] == "cs_semester_1"))
        before = source_envelope(case)
        case["final"]["content"] += " Học kỳ này còn bắt buộc học môn 999999, 99 tín chỉ."
        after = source_envelope(case)
        result["known_counterexample"] = {"original": before, "in_memory_mutant": after, "detected": before["passed"] and not after["passed"]}
        if not result["known_counterexample"]["detected"]:
            raise RuntimeError("Scorer still misses the known counterexample")
    retain(target, result)
    print(json.dumps({k: v for k, v in result.items() if k != "verdicts"}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
