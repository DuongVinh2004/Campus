"""Real HTTP/worker/PostgreSQL/BGE smoke; records exact scope, never claims a corpus benchmark."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime

import httpx

from knowledge_platform import STATE, ROOT, checked_path, retain
from campus247.domain.shared.values import generate_uuid7

BASE = "http://127.0.0.1:8015"
API = "/v1/knowledge/platform"


def require(response, expected=200):
    if response.status_code != expected:
        # Response bodies in this script contain only the explicitly synthetic test content.
        raise AssertionError(f"HTTP {response.status_code}, expected {expected}: {response.text[:1000]}")
    return response.json()


def login(account):
    client = httpx.Client(base_url=BASE, trust_env=False, timeout=90)
    require(client.post(API + "/local-session",json={"account":account}))
    return client


def wait_state(client, condition, *, seconds=120):
    deadline = time.monotonic()+seconds
    while time.monotonic()<deadline:
        state = require(client.get(API+"/state"))
        if condition(state):
            return state
        time.sleep(1)
    raise AssertionError("Timed out waiting for the real worker/runtime")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--chat",action="store_true",help="Exercise the existing paid guarded gateway with synthetic text")
    args=parser.parse_args()
    stamp=datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    report={"at":stamp,"scope":"one synthetic document; actual HTTP, durable worker, PostgreSQL, BGE; not HUCE quality acceptance", "checks":{}}
    report_path=STATE / ("smoke-"+stamp+".json")
    author,reviewer,student=login("KA01"),login("KA02"),login("SV01")
    checks=report["checks"]
    try:
        content=("TÀI LIỆU KIỂM CHỨNG LOCAL — không phải quy định HUCE.\n"
                 "Phòng thí nghiệm Sao Mai mở cửa từ 08:00 đến 17:00 các ngày thứ Hai đến thứ Sáu. "
                 "Vào thứ Bảy và Chủ nhật, phòng đóng cửa. Khi đến phòng, bạn đọc mang theo thẻ bạn đọc.").encode()
        identifier=generate_uuid7()
        input_path=checked_path(STATE / ("smoke-"+stamp+".txt"),ROOT)
        with input_path.open("xb") as stream:
            stream.write(content)
        metadata={"title":"Kiểm chứng local — phòng Sao Mai", "owner_unit":"Nhóm kiểm thử local",
            "canonical_uri":"urn:campus247:local-verification:"+identifier,
            "programs":["PUBLIC"],"audiences":["STUDENT","KNOWLEDGE_ADMIN"],
            "effective_from":"2026-10-01T00:00:00Z"}
        existing = require(author.get(API+"/state"))
        previous = next((s for s in existing["sources"] if s["title"] == metadata["title"]
                         and s["canonical_uri"].startswith("urn:campus247:local-verification:")), None)
        if previous:
            # A rerun creates an immutable new version of the same source. It does
            # not fill release membership with indistinguishable duplicate sources.
            metadata.update(source_id=previous["id"], canonical_uri=previous["canonical_uri"])
        def submit():
            return author.post(API+"/uploads",data={"metadata":json.dumps(metadata,ensure_ascii=False)},
                files={"file":("local-verification.txt",content,"text/plain")},headers={"Idempotency-Key":identifier})
        accepted=require(submit(),202)
        replay=require(submit(),202)
        assert accepted["version_id"]==replay["version_id"] and replay["is_replay"]
        checks["upload_idempotent"]=True
        version_id,job_id=accepted["version_id"],accepted["job_id"]
        report.update(version_id=version_id,job_id=job_id,original_sha256=hashlib.sha256(content).hexdigest())
        assert student.get(API+f"/versions/{version_id}/original").status_code==403
        checks["student_original_denied"]=True
        state=wait_state(author,lambda s:any(j["id"]==job_id and j["state"] in {"SUCCEEDED","FAILED"} for j in s["jobs"]))
        job=next(j for j in state["jobs"] if j["id"]==job_id)
        assert job["state"]=="SUCCEEDED",job
        checks["real_worker_succeeded"]=True
        original=author.get(API+f"/versions/{version_id}/original")
        assert original.status_code==200 and hashlib.sha256(original.content).digest()==hashlib.sha256(content).digest()
        rendition=require(author.get(API+f"/versions/{version_id}/rendition"))
        assert rendition["pages"][0]["page"] is None and not rendition["issues"]
        checks["original_and_locator_verified"]=True
        version=next(v for v in state["versions"] if v["version_id"]==version_id)
        review={"expected_revision":version["revision"],"verdict":"APPROVED",
            "note":"Automated independent-account verification of synthetic fixture; not human or institutional approval."}
        assert author.post(API+f"/versions/{version_id}/reviews",json=review).status_code==403
        require(reviewer.post(API+f"/versions/{version_id}/reviews",json=review))
        checks["separate_reviewer_required"]=True
        release=require(reviewer.post(API+f"/versions/{version_id}/releases",headers={"Idempotency-Key":identifier}),201)
        release_id=release["release_id"]
        report["release_id"]=release_id
        query="Phòng thí nghiệm Sao Mai mở cửa từ mấy giờ đến mấy giờ?"
        started=time.monotonic()
        found=require(reviewer.post(API+"/search-preview",json={"release_id":release_id,"query":query}))
        assert found["items"] and found["items"][0]["document_version_id"]==version_id
        assert "08:00" in found["items"][0]["content_text"]
        report["search_preview_seconds"]=time.monotonic()-started
        report["retrieved_chunk_ids"]=[r["chunk_id"] for r in found["items"]]
        checks["real_bge_pgvector_rrf_rerank"]=True
        body={"operation":"activate","target_id":release_id,"expected_generation":state["desired"]["generation"]}
        assert author.post(API+"/previews",json=body).status_code==403
        preview=require(reviewer.post(API+"/previews",json=body))
        competing=require(reviewer.post(API+"/previews",json=body))
        confirmation={"preview_id":preview["preview_id"],"confirmation_token":preview["confirmation_token"],"confirmed":True}
        confirmed=require(reviewer.post(API+"/confirmations",json=confirmation,headers={"Idempotency-Key":identifier}))
        assert not confirmed["serving_confirmed"]
        replayed=require(reviewer.post(API+"/confirmations",json=confirmation,headers={"Idempotency-Key":identifier}))
        assert replayed["is_replay"]
        assert reviewer.post(API+"/confirmations",json={"preview_id":competing["preview_id"],"confirmation_token":competing["confirmation_token"],"confirmed":True},headers={"Idempotency-Key":generate_uuid7()}).status_code==409
        checks["activation_cas_and_idempotency"]=True
        state=wait_state(reviewer,lambda s:s["is_serving"] and s["desired"]["release_id"]==release_id)
        checks["fresh_runtime_ack"]=True
        report["serving"]=state["serving"]
        if args.chat:
            conversation=require(student.post("/v1/conversations",json={"mode":"temporary"}),201)
            conversation_id=conversation.get("conversation_id",conversation.get("id"))
            response=student.post(f"/v1/conversations/{conversation_id}/messages:stream",json={"content":query,"client_id":generate_uuid7()})
            assert response.status_code==200
            events=[]
            for block in response.text.split("\n\n"):
                name=next((l[7:] for l in block.splitlines() if l.startswith("event: ")),None)
                data=next((l[6:] for l in block.splitlines() if l.startswith("data: ")),None)
                if name and data:
                    events.append({"event":name,"data":json.loads(data)})
            report["chat_events"]=events
            completed=next((e["data"] for e in events if e["event"]=="message.completed"),None)
            assert completed and completed["status"]=="answered",completed
            citation_event=next(e["data"] for e in events if e["event"]=="citation.added")
            citation=citation_event["citation"]["citation"]
            assert citation["document_version_id"]==version_id and citation["release_id"]==release_id
            source_path=f'/v1/conversations/{conversation_id}/messages/{citation_event["message_id"]}/citations/{citation["citation_id"]}/source'
            source=require(student.get(source_path))
            assert "08:00" in source["content_text"]
            report["citation_path"]=source_path
            checks["real_chat_and_authorized_source"]=True
        revoke=require(reviewer.post(API+"/previews",json={"operation":"revoke","target_id":version_id,"expected_generation":state["desired"]["generation"]}))
        require(reviewer.post(API+"/confirmations",json={"preview_id":revoke["preview_id"],"confirmation_token":revoke["confirmation_token"],"confirmed":True},headers={"Idempotency-Key":generate_uuid7()}))
        if args.chat:
            assert student.get(report["citation_path"]).status_code in {404,503}
        state=require(reviewer.get(API+"/state"))
        rollback=require(reviewer.post(API+"/previews",json={"operation":"rollback","target_id":release_id,"expected_generation":state["desired"]["generation"]}))
        require(reviewer.post(API+"/confirmations",json={"preview_id":rollback["preview_id"],"confirmation_token":rollback["confirmation_token"],"confirmed":True},headers={"Idempotency-Key":generate_uuid7()}))
        state=require(reviewer.get(API+"/state"))
        assert next(v for v in state["versions"] if v["version_id"]==version_id)["revoked_at"]
        if args.chat:
            assert student.get(report["citation_path"]).status_code in {404,503}
        checks["revocation_survives_rollback"]=True
        report["passed"]=True
    except Exception as error:
        report["passed"]=False
        report["failure_type"],report["failure"]=type(error).__name__,str(error)[:2000]
        raise
    finally:
        for client in (author,reviewer,student):
            client.close()
        retain(report_path,report)
        print(json.dumps({"report":str(report_path),"passed":report.get("passed"),"checks":checks}),flush=True)


if __name__=="__main__":
    main()
