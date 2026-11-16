"""Verify the approved main deployment, old evidence and one actual answer."""
import asyncio
import argparse
from datetime import UTC, datetime
import hashlib
import json
import sqlite3
import time

import httpx

from knowledge_platform import ROOT, STATE, TENANT, checked_path, connection, model_budget, retain
from knowledge_automation_checkpoint_20261027 import database
from knowledge_automation_live_eval import paid
from knowledge_automation_conversation_probe import PLAN
from verify_knowledge_platform_huce import final
from campus247.infrastructure.repositories.sqlite_conversations import message
from campus247.application.conversation.read import final_payload
from campus247.domain.shared.values import generate_uuid7


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--existing-receipt", help="Verify this exact already-generated main answer without another model request")
    args = parser.parse_args()
    scope = ROOT / "infra/local/knowledge-automation-20261026"
    existing = None
    if args.existing_receipt:
        prior = checked_path((ROOT / args.existing_receipt).absolute(),ROOT)
        if prior.parent.parent != scope or prior.name != "receipt.json" or not prior.parent.name.startswith("main-rollout-check-"):
            raise ValueError("Exact retained main smoke receipt required")
        existing = json.loads(prior.read_bytes())
    target = scope / ("main-rollout-check-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f"))
    expected = PLAN[-1]["turns"][0]
    retain(target / "plan.json", {"question":expected,"retries":0,"scope":"one bounded operational deployment smoke; no institution-wide acceptance"})
    owner = json.loads((STATE / "owner-identity.json").read_bytes())
    report = {"at":datetime.now(UTC),"paid_before":paid(),"native_before":model_budget(),"checks":{},"historical_citation":None,
        "fresh_generation_requested":existing is None,"answer_basis":args.existing_receipt or "new actual main request"}
    db = sqlite3.connect((STATE / "conversations.sqlite3").as_uri()+"?mode=ro",uri=True)
    historical = []
    try:
        for (raw,) in db.execute("SELECT m.record FROM message m JOIN conversation c ON c.id=m.conversation_id WHERE c.owner=? ORDER BY m.rowid DESC LIMIT 2000",(owner["owner_id"],)):
            item = message(raw)
            result = final_payload(item)
            if result and result["response_class"] in {"grounded_answer","partial_answer"}:
                historical.extend((item.conversation_id,item.id,c["citation"]) for c in result["citations"])
                if len(historical)>=20:
                    break
    finally:
        db.close()
    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8015",trust_env=False,timeout=90) as client:
            response = await client.get("/v1/knowledge/platform/state")
            report["checks"]["anonymous_admin_denied"] = response.status_code == 401
            credentials = json.loads((STATE / "owner-credentials.json").read_bytes())
            login = await client.post("/v1/knowledge/platform/session",json={key:credentials[key] for key in ("username","password")})
            credentials = None
            login.raise_for_status()
            body = login.json()
            report["checks"]["existing_owner"] = body["user_id"] == owner["owner_id"] and body.get("is_synthetic_identity") is False
            client.headers["Authorization"] = "Bearer "+body["token"]
            body = None
            response = await client.get("/v1/knowledge/platform/state"); response.raise_for_status()
            state = response.json()
            report["runtime"] = {key:state[key] for key in ("environment","desired","is_serving")}
            report["live_acks"] = [row for row in state["serving"] if row.get("live")]
            report["checks"]["operational_ack"] = state["environment"] == "operational" and state["is_serving"]
            source = next(row for row in state["versions"] if row["is_in_desired_release"] and not row["revoked_at"])
            response = await client.get("/v1/knowledge/platform/versions/"+source["version_id"]+"/original")
            report["checks"]["original_hash"] = response.status_code == 200 and hashlib.sha256(response.content).hexdigest() == source["original_sha256"]
            for cid,mid,citation in historical:
                path = f"/v1/conversations/{cid}/messages/{mid}/citations/{citation['citation_id']}/source"
                response = await client.get(path)
                if response.status_code == 200:
                    payload = response.json()
                    report["historical_citation"] = {"conversation_id":cid,"message_id":mid,"citation_id":citation["citation_id"],
                        "hash_valid":hashlib.sha256(payload["content_text"].encode()).hexdigest() == citation["evidence_sha256"],
                        "locator_matches":payload["citation"]["locator"] == citation["locator"]}
                    history = await client.get(f"/v1/conversations/{cid}/messages")
                    report["checks"]["old_history"] = history.status_code == 200
                    break
            report["checks"]["old_citation"] = bool(report["historical_citation"] and report["historical_citation"]["hash_valid"] and report["historical_citation"]["locator_matches"])
            if existing:
                report["answer"] = {**existing["answer"],"citations":[]}
                cid,client_id,result = (report["answer"][key] for key in ("conversation_id","client_id","final"))
            else:
                response = await client.post("/v1/conversations",json={"mode":"temporary"}); response.raise_for_status()
                cid = response.json()["id"]
                client_id = generate_uuid7()
                started = time.perf_counter()
                response = await client.post(f"/v1/conversations/{cid}/messages:stream",json={"content":expected["question"],"client_id":client_id})
                with (target / "answer.sse").open("xb") as output:
                    output.write(response.content)
                result = final(response.text.replace("\r\n","\n"))
                report["answer"] = {"http_status":response.status_code,"conversation_id":cid,"client_id":client_id,
                    "elapsed_seconds":time.perf_counter()-started,"final":result,"citations":[]}
            request = {"content":expected["question"],"client_id":client_id}
            report["checks"]["actual_answer"] = bool(report["answer"]["http_status"] == 200 and result and result["status"] == "answered"
                and all(term in result["content"] for term in expected["required"]))
            sources = set()
            for wrapped in (result or {}).get("citations",[]):
                citation = wrapped["citation"]
                sources.add(citation["source_id"])
                path = f"/v1/conversations/{cid}/messages/{result['message_id']}/citations/{citation['citation_id']}/source"
                response = await client.get(path)
                payload = response.json()
                async with httpx.AsyncClient(base_url="http://127.0.0.1:8015",trust_env=False) as anonymous:
                    anonymous_status = (await anonymous.get(path)).status_code
                report["answer"]["citations"].append({"status":response.status_code,"anonymous_status":anonymous_status,
                    "hash_valid":hashlib.sha256(payload.get("content_text","").encode()).hexdigest() == citation["evidence_sha256"]})
            report["checks"]["two_source_readback"] = sources == set(expected["sources"]) and all(
                row["status"] == 200 and row["anonymous_status"] == 401 and row["hash_valid"] for row in report["answer"]["citations"])
            before_replay = paid()
            response = await client.post(f"/v1/conversations/{cid}/messages:stream",json=request)
            with (target / "duplicate-response.body").open("xb") as output:
                output.write(response.content)
            receipt_path = f"/v1/conversations/{cid}/receipts/{client_id}"
            stored = await client.get(receipt_path)
            receipt = stored.json()
            report["duplicate_request"] = {"http_status":response.status_code,"receipt_http_status":stored.status_code,
                "receipt":receipt,"paid_unchanged":paid() == before_replay}
            # The existing API contract deliberately returns409 plus the durable
            # receipt URL. It does not regenerate/replay a second SSE answer.
            report["checks"]["idempotent_replay"] = bool(result and response.status_code == 409
                and response.json().get("receipt_path") == receipt_path and stored.status_code == 200
                and receipt["state"] == "completed" and receipt["assistant_message_id"] == result["message_id"]
                and report["duplicate_request"]["paid_unchanged"])
            report["checks"]["new_history"] = (await client.get(f"/v1/conversations/{cid}/messages")).status_code == 200
            report["checks"]["logout"] = (await client.post("/v1/auth/logout")).status_code == 200
            report["checks"]["revoked_session_denied"] = (await client.get("/v1/knowledge/platform/state")).status_code == 401
    finally:
        report["database"] = await database(connection())
        report["checks"]["schema_and_counts"] = (report["database"]["schema"],report["database"]["source_count"],report["database"]["version_count"],report["database"]["serving_members"]) == ("0022",120,330,114)
        report.update(finished_at=datetime.now(UTC),paid_after=paid(),native_after=model_budget())
        report["all_passed"] = all(report["checks"].values()) and len(report["checks"]) == 13
        retain(target / "receipt.json",report)
        print(json.dumps({"receipt":str(target / "receipt.json"),"all_passed":report["all_passed"],"checks":report["checks"]}))
    if not report["all_passed"]:
        raise RuntimeError("Main smoke incomplete; inspect retained evidence")


if __name__ == "__main__":
    asyncio.run(main())
