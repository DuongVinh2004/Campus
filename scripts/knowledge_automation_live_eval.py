"""At most12 frozen questions through an existing guarded writer, no retries.

Uses the installed gateway's existing budget/lease/accounting. Never changes a
cap, creates a reviewer, or activates a release. Existing-runtime mode is an
explicit additive conversation baseline, never candidate-code acceptance.
"""
import argparse
import hashlib
import json
import time
from datetime import UTC, datetime

import httpx

from knowledge_platform import ROOT, STATE, DB_NAME, checked_path, rehearsal_bundle_paths, retain, model_budget
from multi_agent_live_resources import latest_paid_snapshot
from verify_knowledge_platform_huce import final


def paid():
    value=latest_paid_snapshot()
    return {key:value[key] for key in ("calls","input_tokens_charged","output_tokens_charged","conservative_charged_usd","unsettled_attempts_retained")}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--manifest",required=True)
    parser.add_argument("--gold",required=True)
    parser.add_argument("--port",type=int,choices=(8015,8017,8018),default=8017)
    parser.add_argument("--baseline-existing",action="store_true",help="Use current8015 writer for an additive baseline; no gateway/lease replacement")
    parser.add_argument("--limit",type=int,help="Explicit bounded diagnostic subset; never reports a complete shard")
    parser.add_argument("--start-index",type=int,default=0,help="Continue with the remaining frozen questions without rerunning earlier answers")
    args=parser.parse_args()
    if (args.port==8015)!=args.baseline_existing:
        raise ValueError("8015 requires explicit existing-runtime baseline mode; other ports require restored-runtime mode")
    manifest=checked_path(ROOT / args.manifest,ROOT)
    if not rehearsal_bundle_paths(manifest): raise ValueError("Complete verified restore bundle required")
    binding=json.loads(manifest.read_text(encoding="utf-8"))
    gold_path=checked_path(ROOT / args.gold,ROOT)
    raw=gold_path.read_bytes(); gold=json.loads(raw)
    if not 1<=len(gold["cases"])<=12 or len({case["name"] for case in gold["cases"]})!=len(gold["cases"]):
        raise ValueError("One frozen bounded shard required")
    if args.limit is not None and not 1<=args.limit<=len(gold["cases"]): raise ValueError("Limit must stay within the frozen shard")
    if not 0<=args.start_index<len(gold["cases"]): raise ValueError("Start index must stay within the frozen shard")
    selected=gold["cases"][args.start_index:args.start_index+args.limit if args.limit is not None else None]
    for path,key in ((gold["witness_file"],"witness_file_sha256"),(gold["original_file"],"original_sha256")):
        if hashlib.sha256(checked_path(ROOT / path,ROOT).read_bytes()).hexdigest()!=gold[key]: raise ValueError("Gold witness binding changed")
    scope=checked_path(ROOT / "infra/local/knowledge-automation-20261026" / ("live-independent-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")),ROOT)
    scope.mkdir()
    report={"started_at":datetime.now(UTC).isoformat(),"gold":str(gold_path),"gold_sha256":hashlib.sha256(raw).hexdigest(),
        "manifest":str(manifest),"source_snapshot_database":binding["database"],"execution_database":DB_NAME if args.baseline_existing else binding["database"],
        "runner_sha256":hashlib.sha256(__import__("pathlib").Path(__file__).read_bytes()).hexdigest(),"selected_count":len(selected),"start_index":args.start_index,
        "port":args.port,"native_before":model_budget(),"paid_before":paid(),"cases":[],
        "scope":"regulation-text shard, not full P00-P16 acceptance; deterministic flags require semantic adjudication","request_retry_count":0,
        "mode":"existing-runtime baseline; candidate code not evaluated" if args.baseline_existing else "restored runtime",
        "mutation_scope":"fresh conversations and this checker's login/logout only; no source/schema/review/release change"}
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{args.port}",trust_env=False,timeout=90,follow_redirects=False) as client:
            credentials=json.loads((STATE / "owner-credentials.json").read_text(encoding="utf-8"))
            login=client.post("/v1/knowledge/platform/session",json={key:credentials[key] for key in ("username","password")})
            credentials=None; login.raise_for_status()
            state=client.get("/v1/knowledge/platform/state"); state.raise_for_status(); state=state.json()
            if (not args.baseline_existing and state.get("environment")!="rehearsal") or not state["is_serving"] or state["desired"]!=binding["source_pointer"]:
                raise ValueError("Restored runtime binding differs from the frozen source snapshot")
            report.update(desired=state["desired"],serving=state["serving"])
            for case in selected:
                budget=model_budget()
                if budget["remaining_inferences"] is not None and budget["remaining_inferences"]<4:
                    report["not_run_reason"]="Existing bounded native budget cannot cover another question"; break
                started=time.perf_counter()
                conversation=client.post("/v1/conversations",json={"mode":"temporary"}); conversation.raise_for_status()
                cid=conversation.json()["id"]
                from campus247.domain.shared.values import generate_uuid7
                client_id=generate_uuid7()
                response=client.post(f"/v1/conversations/{cid}/messages:stream",json={"content":case["question"],"client_id":client_id})
                stream=checked_path(scope / ("stream-"+str(len(report["cases"])+1).zfill(2)+".sse"),ROOT)
                with stream.open("xb") as output: output.write(response.content)
                result=final(response.text.replace("\r\n","\n"))
                events=[]
                for frame in response.text.replace("\r\n","\n").split("\n\n"):
                    kind=next((line[7:] for line in frame.splitlines() if line.startswith("event: ")),None)
                    data=next((line[6:] for line in frame.splitlines() if line.startswith("data: ")),None)
                    if kind: events.append({"event":kind,**({"failure":json.loads(data)} if kind=="message.failed" and data else {})})
                sources=[]
                for mapping in (result or {}).get("citations",[]):
                    citation=mapping["citation"]
                    source=client.get(f"/v1/conversations/{cid}/messages/{result['message_id']}/citations/{citation['citation_id']}/source")
                    sources.append({"status":source.status_code,"body":source.json()})
                row={"name":case["name"],"question":case["question"],"conversation_id":cid,"http_status":response.status_code,
                    "final":result,"sources":sources,"events":events,"stream_file":str(stream.relative_to(ROOT)),"client_id":client_id,
                    "elapsed_seconds":time.perf_counter()-started,"native_after":model_budget(),"paid_after":paid()}
                report["cases"].append(row)
                # Sequential numeric receipt names never use an untrusted case name as a path.
                retain(scope / ("case-"+str(len(report["cases"])).zfill(2)+".json"),row)
                print(json.dumps({"case":case["name"],"status":(result or {}).get("status"),"sources":len(sources),"elapsed_seconds":row["elapsed_seconds"]}),flush=True)
                if response.status_code!=200 or result is None:
                    report["not_run_reason"]="HTTP/final failure retained; no automatic retry or continuing provider campaign"; break
            client.post("/v1/auth/logout")  # Only this fresh checker-created session, never the user's browser session.
    finally:
        report.update(finished_at=datetime.now(UTC).isoformat(),native_after=model_budget(),paid_after=paid())
        report["all_frozen_cases_ran"]=len(report["cases"])==len(gold["cases"])
        report["usage_attribution"]="Shared native/paid ledgers; aggregate differences may include concurrent requests, not agent quota delta"
        retain(scope / "receipt.json",report)
        print(json.dumps({"receipt":str(scope / "receipt.json"),"cases":len(report["cases"]),"all_frozen_cases_ran":report["all_frozen_cases_ran"]}),flush=True)


if __name__=="__main__": main()
