"""Combine explicitly segmented observations while preserving every failed attempt.

Latest terminal observation is used per frozen question, never highest-scoring
answer selection. First-attempt reliability and all immutable input receipts
remain visible; this is an existing-runtime baseline, not candidate acceptance.
"""
import argparse
import hashlib
import json
from datetime import datetime
from decimal import Decimal

from knowledge_platform import ROOT, DB_NAME, checked_path, retain


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--gold",required=True)
    parser.add_argument("--receipts",nargs="+",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    gold_file=checked_path(ROOT / args.gold,ROOT); gold_raw=gold_file.read_bytes(); gold=json.loads(gold_raw)
    expected={case["name"]:case for case in gold["cases"]}; reports=[]
    if not 1<=len(args.receipts)<=4: raise ValueError("Small explicit receipt set required")
    for name in args.receipts:
        path=checked_path(ROOT / name,ROOT); raw=path.read_bytes(); report=json.loads(raw)
        if report["gold_sha256"]!=hashlib.sha256(gold_raw).hexdigest() or report.get("port")!=8015 or not report.get("mode","").startswith("existing-runtime baseline"):
            raise ValueError("Only the exact frozen baseline shard can be assembled")
        reports.append((report,path,hashlib.sha256(raw).hexdigest()))
    reports.sort(key=lambda entry:datetime.fromisoformat(entry[0]["started_at"]))
    desired=reports[0][0]["desired"]; latest,first,attempts={},{},[]
    for report,path,sha in reports:
        if report["desired"]!=desired: raise ValueError("Snapshot changed between segments")
        for row in report["cases"]:
            if row["name"] not in expected or row["question"]!=expected[row["name"]]["question"]:
                raise ValueError("Question differs from frozen gold")
            provenance={"receipt":str(path.relative_to(ROOT)),"receipt_sha256":sha,"row_sha256":hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
            attempts.append({"name":row["name"],"http_status":row["http_status"],"status":(row.get("final") or {}).get("status"),"terminal_final_present":row.get("final") is not None,**provenance})
            first.setdefault(row["name"],row); latest[row["name"]]={**row,"provenance":provenance}
    if set(latest)!=set(expected): raise ValueError("Shard incomplete; keep segmented receipts without an all-case claim")
    before,after=reports[0][0]["paid_before"],reports[-1][0]["paid_after"]
    result={"gold_sha256":hashlib.sha256(gold_raw).hexdigest(),"cases":[latest[case["name"]] for case in gold["cases"]],
        "attempts":attempts,"attempt_count":len(attempts),"unique_questions":len(expected),"desired":desired,"execution_database":DB_NAME,
        "candidate_code_evaluated":False,"mode":"segmented existing-runtime baseline with all attempts retained",
        "first_attempt_final_missing":sum(row.get("final") is None for row in first.values()),
        "first_attempt_disposition_matches":sum((row.get("final") or {}).get("status")==expected[name]["status"] for name,row in first.items()),
        "latest_disposition_matches":sum((row.get("final") or {}).get("status")==expected[name]["status"] for name,row in latest.items()),
        "shared_paid_ledger_delta":{"calls":after["calls"]-before["calls"],"input_tokens":after["input_tokens_charged"]-before["input_tokens_charged"],
            "output_tokens":after["output_tokens_charged"]-before["output_tokens_charged"],"conservative_usd":str(Decimal(after["conservative_charged_usd"])-Decimal(before["conservative_charged_usd"]))},
        "limitations":["One initial missing-final attempt is retained; first-question diagnostic and remaining10 were separate explicit segments",
            "The first raw report's database field refers to the source backup copy; actual endpoint was8015 and execution DB is stated here",
            "Ledger deltas are aggregate shared counters; not exclusively attributable or an agent quota delta",
            "Literal scoring requires semantic adjudication; no whole-product acceptance"]}
    target=checked_path(ROOT / args.output,ROOT); retain(target,result)
    print(json.dumps({key:result[key] for key in ("attempt_count","unique_questions","first_attempt_final_missing","first_attempt_disposition_matches","latest_disposition_matches","shared_paid_ledger_delta")}))


if __name__=="__main__": main()
