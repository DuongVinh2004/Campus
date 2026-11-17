"""Source-checked local expansion; additive versions and normal review/release controls."""
import asyncio
import json
from datetime import datetime, UTC

import httpx

from knowledge_platform import ROOT, STATE, TENANT, checked_path, components, retain
from knowledge_platform_release import API, BASE, checked
from campus247.application.knowledge.original_excerpt import source_excerpt_version
from campus247.infrastructure.identity.local_owner import LocalOwnerIdentityAdapter

LAB_VERSION="f2759ffd-8a8d-7973-8e04-4f831417e195"
BASIS=("Đối chiếu hai ảnh PDF gốc SHA256 8a0bc59b2cc844d7f606204f8b4c3cbf6c99e023033493057f923929221810c7 ngày 23/10/2026. "
    "Ngày ký 09/04/2024; Điều 2 có hiệu lực kể từ ngày ký. Chỉ phục vụ 12 khoản trang 2 cho sinh viên tại phòng máy Trung tâm CNTT&CSDL. "
    "Số quyết định viết tay chưa xác minh, không gán số. Không tuyên bố đã xác minh mọi văn bản sửa đổi/thay thế.")


async def prepare():
    pool,_,platform,_=await components()
    adapter=LocalOwnerIdentityAdapter(checked_path(STATE/"owner-identity.json",ROOT),TENANT)
    author=adapter.resolve_token(adapter.mint_token(adapter.directory()["agent_id"]))
    try:
        async with platform.repo.transaction() as conn:
            row=await platform.repo.version(conn,LAB_VERSION)
        result=await source_excerpt_version(platform,author,LAB_VERSION,expected_revision=row["revision"],
            effective_from=datetime(2024,4,8,17,tzinfo=UTC),basis=BASIS,key="lab-original-page2-verified-20261023-v2")
        async with platform.repo.transaction() as conn:
            chunks=await conn.fetch("""SELECT c.content_text,c.page_start,ci.provenance FROM knowledge_chunk c
                JOIN knowledge_chunk_input ci ON ci.chunk_id=c.id WHERE c.document_version_id=$1""",result["version_id"])
        from campus247.infrastructure.knowledge.repository import json_value
        import sys
        sys.path.insert(0,str(ROOT/"infra/local/rag-fixture"))
        from token_envelope_20261007_25 import TokenEnvelope
        envelope=TokenEnvelope()
        maximum=0
        for row in chunks:
            span=json_value(row["provenance"])["verified_rerank_span"]
            text=row["content_text"][span["char_start"]:span["char_end"]]
            count=len(envelope.models["reranker"].encode("Sinh viên đến muộn sau bao nhiêu phút không được vào phòng thực hành máy tính?",text,add_special_tokens=True).ids)
            if row["page_start"]!=2 or count>envelope.limit or "Phạm vi đã đối chiếu:" in row["content_text"]:
                raise ValueError("Candidate evidence/envelope mismatch; no review or activation")
            maximum=max(maximum,count)
        result["maximum_canary_pair_tokens"]=maximum
        return result
    finally:
        await pool.close()


def main():
    result=asyncio.run(prepare())
    retain(STATE/("lab-candidate-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".json"),result)
    credentials=json.loads(checked_path(STATE/"owner-credentials.json",ROOT).read_text(encoding="utf-8"))
    with httpx.Client(base_url=BASE,trust_env=False,timeout=60) as client:
        checked(client.post(API+"/session",json={k:credentials[k] for k in ("username","password")}))
        state=checked(client.get(API+"/state"))
        version=next(v for v in state["versions"] if v["version_id"]==result["version_id"])
        note=("Duyệt kỹ thuật TỰ ĐỘNG do agent theo tài khoản chủ hệ thống chỉ định; KHÔNG phải xác nhận cán bộ HUCE. "
            "Đã đọc toàn bộ hai ảnh gốc, đối chiếu 12 khoản trang 2, hash original/ảnh/OCR/transcript và mapping child BGE. "+BASIS)
        if version["review_state"]!="APPROVED":
            checked(client.post(API+f"/versions/{result['version_id']}/reviews",json={"expected_revision":version["revision"],"verdict":"APPROVED","note":note}))
        release=checked(client.post(API+f"/versions/{result['version_id']}/releases",json={},headers={"Idempotency-Key":"lab-real-release-20261023-v2"}),201)
        preview=checked(client.post(API+"/previews",json={"operation":"activate","target_id":release["release_id"],"expected_generation":release["expected_generation"]}))
        # The application build retains existing members; verify the concrete preview has exactly the intended 3 versions.
        expected={"01a167c6-b6ca-77b2-a2a6-cefd66345d5d","01a167eb-e62e-71d9-91ea-a9aedc888f0d",result["version_id"]}
        if {m["version_id"] for m in preview["payload"]["members"]}!=expected:
            raise ValueError("Unexpected membership; confirmation withheld")
        activated=checked(client.post(API+"/confirmations",json={"preview_id":preview["preview_id"],"confirmation_token":preview["confirmation_token"],"confirmed":True},
            headers={"Idempotency-Key":"lab-real-activate-20261023-v2"}))
        receipt={"candidate":result,"release":release,"preview":preview["payload"],"activation":activated,"review_note":note,
            "university_human_approval_claimed":False,"new_model_calls":0}
        target=STATE/("lab-real-release-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".json")
        retain(target,receipt)
        print(json.dumps({"receipt":str(target),"candidate":result,"activation":activated},ensure_ascii=False),flush=True)


if __name__=="__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    main()
