"""Exercise a complete restored runtime with the existing designated owner.

No token/credential, conversation text or citation text is written to receipts.
Logout revokes only the new session created by this check, in the restored store.
"""
import argparse
import asyncio
import hashlib
import json
import sqlite3
from datetime import UTC, datetime

import httpx

from knowledge_platform import ROOT, STATE, TENANT, checked_path, components, rehearsal_bundle_paths, retain
from campus247.infrastructure.repositories.sqlite_conversations import message
from campus247.application.conversation.read import final_payload


async def inspect(manifest):
    paths = rehearsal_bundle_paths(manifest)
    if not paths: raise ValueError("A complete verified bundle is required")
    report = {"at":datetime.now(UTC).isoformat(),"manifest":str(manifest),"new_model_calls":0,"url":"http://127.0.0.1:8017",
        "model_scope":"runtime health/metadata and source reads only; no embedding, reranking or generation request",
        "sqlite_binding":{name:str(path) for name,path in paths.items() if name!="artifacts"},"artifact_binding":str(paths["artifacts"])}
    directory = json.loads((STATE / "owner-identity.json").read_text(encoding="utf-8"))
    credentials = json.loads((STATE / "owner-credentials.json").read_text(encoding="utf-8"))
    convdb = sqlite3.connect(paths["conversations.sqlite3"].as_uri()+"?mode=ro",uri=True)
    citations = []
    try:
        for (encoded,) in convdb.execute("""SELECT m.record FROM message m JOIN conversation c ON c.id=m.conversation_id
            WHERE c.owner=? ORDER BY m.rowid DESC LIMIT 2000""",(directory["owner_id"],)):
            item = message(encoded)
            final = final_payload(item)
            if final and final["response_class"] in {"grounded_answer","partial_answer"}:
                for witness in final["citations"]:
                    citation = witness["citation"]
                    citations.append((item.conversation_id,item.id,citation))
                    if len(citations)>=20: break
            if len(citations)>=20: break
    finally:
        convdb.close()
    async with httpx.AsyncClient(base_url=report["url"],trust_env=False,timeout=30,follow_redirects=False) as client:
        public = await client.get("/v1/knowledge/platform/availability")
        report["public_availability_status"] = public.status_code
        anonymous = await client.get("/v1/knowledge/platform/state")
        report["anonymous_admin_read_denied"] = anonymous.status_code in {401,403}
        login = await client.post("/v1/knowledge/platform/session",json=credentials)
        credentials = None
        if login.status_code != 200: raise RuntimeError("Existing owner login failed on restored runtime")
        body = login.json()
        if body.get("is_synthetic_identity") is not False or body.get("user_id") != directory["owner_id"]:
            raise RuntimeError("Restored runtime did not resolve the designated real local owner")
        client.headers["Authorization"] = "Bearer "+body["token"]
        token = body["token"]; body = None
        state = await client.get("/v1/knowledge/platform/state")
        if state.status_code != 200: raise RuntimeError("Restored owner state read failed")
        body = state.json()
        report["state_status"] = state.status_code
        report["desired"] = body["desired"]
        report["is_serving"] = body["is_serving"]
        report["serving_acks"] = body["serving"]
        source = next(version for version in body["versions"] if version["is_in_desired_release"] and not version["revoked_at"])
        original = await client.get("/v1/knowledge/platform/versions/"+source["version_id"]+"/original")
        report["original_read"] = {"status":original.status_code,"sha256":hashlib.sha256(original.content).hexdigest(),
            "matches_expected":hashlib.sha256(original.content).hexdigest()==source["original_sha256"]}
        report["owned_historical_citation_candidates"] = len(citations)
        report["historical_citation"] = None
        for conversation_id,message_id,citation in citations:
            response = await client.get(f"/v1/conversations/{conversation_id}/messages/{message_id}/citations/{citation['citation_id']}/source")
            if response.status_code == 200:
                payload = response.json()
                report["historical_citation"] = {"status":200,"content_sha256":payload["content_sha256"],
                    "content_hash_matches":hashlib.sha256(payload["content_text"].encode()).hexdigest()==payload["content_sha256"],
                    "stored_evidence_matches":citation.get("evidence_sha256") in {None,payload["content_sha256"]},
                    "locator_matches":payload["citation"]["locator"]==citation["locator"]}
                break
        logout = await client.post("/v1/auth/logout")
        report["fresh_test_session_logout_status"] = logout.status_code
        denied = await client.get("/v1/knowledge/platform/state")
        report["revoked_session_denied"] = denied.status_code in {401,403}
        report["fresh_test_session_revocation_key_sha256"] = hashlib.sha256(token.encode()).hexdigest()
        token = None
    pool,_,platform,_ = await components(rehearsal=manifest)
    try:
        async with pool.acquire() as conn:
            report["actual_database"] = await conn.fetchval("SELECT current_database()")
            report["actual_schema"] = await conn.fetchval("SELECT version_num FROM alembic_version")
            ack = await conn.fetchrow("SELECT boot_id,release_id,generation,policy_generation,valid_until>clock_timestamp() AS live FROM knowledge_runtime_ack WHERE tenant_id=$1 AND instance_id='knowledge-local-api'",TENANT)
            report["new_runtime_ack"] = dict(ack)
    finally:
        await pool.close()
    required = (report["anonymous_admin_read_denied"],report["is_serving"],report["original_read"]["matches_expected"],report["revoked_session_denied"],report["new_runtime_ack"]["live"])
    report["runtime_checks_passed"] = all(required)
    report["limits"] = ["No paid answer generation or load campaign", "Other retained test tenants' artifact stores are outside the operational tenant backup scope",
        "A historical citation check requires an existing citation owned by the designated account; no message or reviewer is fabricated"]
    target = checked_path(ROOT / "infra/local/knowledge-automation-20261026" / ("restore-runtime-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".json"),ROOT)
    retain(target,report)
    print(json.dumps({"receipt":str(target),"runtime_checks_passed":report["runtime_checks_passed"],"historical_citation_verified":bool(report["historical_citation"])}))
    if not all(required): raise RuntimeError("Restored runtime check failed; receipt retained")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest",required=True)
    args = parser.parse_args()
    asyncio.run(inspect(checked_path((ROOT / args.manifest).absolute(),ROOT)))


if __name__ == "__main__": main()
