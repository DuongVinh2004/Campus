"""Publish only the three verified text-cleaning replacements, retaining all members."""
import asyncio
import json
import time
from contextlib import closing
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client
from complete_huce_corpus import SCOPE, actors, read
from knowledge_platform import ROOT, TENANT, components, retain
from campus247.application.knowledge.platform_models import digest
from campus247.domain.shared.values import generate_uuid7


def activate():
    previous = read(SCOPE / "candidate-release-05.json"); target = read(SCOPE / "candidate-release-06.json")
    probes = read(SCOPE / "clean-source-probes-01.json")
    assert probes["all_passed"] and probes["release_id"] == target["release_id"]
    old = {row["source_id"]: row for row in previous["members"]}; new = {row["source_id"]: row for row in target["members"]}
    changed = {key for key in new if old[key] != new[key]}
    assert changed == {row["source_id"] for row in probes["cases"]} and len(new) == 114
    assert all(new[row["source_id"]]["version_id"] == row["version_id"] for row in probes["cases"])
    with closing(client()) as c:
        state = c.get(API + "/state").json()
        assert state["desired"]["release_id"] == previous["release_id"] and state["desired"]["generation"] == 14
        response = c.post(API + "/previews", json={"operation": "activate", "target_id": target["release_id"], "expected_generation": 14})
        response.raise_for_status(); preview = response.json()
        assert preview["payload"]["target_sha256"] == target["membership_sha256"]
        assert {row["source_id"]: row for row in preview["payload"]["members"]} == new
        retain(SCOPE / "activation-preview-03.json", {key: value for key,value in preview.items() if key != "confirmation_token"})
        response = c.post(API + "/confirmations", headers={"Idempotency-Key": "huce-clean-source-20261024-activate-01"},
            json={"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"], "confirmed": True})
        response.raise_for_status(); retain(SCOPE / "activation-confirmation-03.json", response.json())
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            state = c.get(API + "/state").json(); availability = c.get(API + "/availability").json()
            if state["is_serving"] and state["desired"]["release_id"] == target["release_id"] and availability["generation"] == 15: break
            time.sleep(.5)
        else: raise RuntimeError("Runtime acknowledgement not verified")
        assert availability["serving_documents"] == 114 and availability["equivalent_sources"] == 3
        retain(SCOPE / "activation-ready-03.json", {"at": datetime.now(UTC).isoformat(), "desired": state["desired"],
            "serving": state["serving"], "availability": availability, "changed_sources": sorted(changed), "unchanged_members": 111})
        print(json.dumps({"release_id": target["release_id"], "generation": 15, "members": 114, "cleaned_sources": 3}))


async def classify():
    record = read(SCOPE / "source-dispositions-02.json"); plan = read(SCOPE / "candidate-plan-06.json")
    entries = {row["source_id"]: row for row in plan["sources"]}
    changed = {row["source_id"] for row in read(SCOPE / "clean-source-probes-01.json")["cases"]}
    pool, _, platform, _ = await components(); _, owner = actors(); platform.admin(owner)
    try:
        for row in record["sources"]:
            if row["source_id"] not in changed: continue
            candidate = read(ROOT / entries[row["source_id"]]["candidate"])
            row["note"] += (" Đã loại điều hướng Previous/Next Post khỏi bài gốc." if row["source_id"] != "129ba0a6-652e-70b8-8532-8e63661262ce" else
                " Đã sửa ký tự OCR ở trang 2 theo ảnh gốc; giữ giới hạn các điều khoản đã chọn và bốn trang mẫu đơn chưa phiên âm.")
            row["evidence"] = {"plan": "candidate-plan-06.json", "candidate_sha256": entries[row["source_id"]]["candidate_sha256"],
                "applicability": candidate["applicability"], "review_witness": candidate["extracted"]["review_witness"], "university_approval_claimed": False}
            fingerprint = digest(row)
            async with platform.repo.transaction() as conn:
                key = "corpus-clean-source-disposition-20261024:" + row["source_id"]
                replay = await platform.repo.replay(conn, owner.subject_id, key, fingerprint)
                if not replay:
                    identifier = generate_uuid7()
                    await conn.execute("""INSERT INTO knowledge_source_disposition(id,tenant_id,source_id,original_sha256,category,
                        related_source_id,note,evidence,created_by) VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9)""", identifier, TENANT,
                        row["source_id"], row["original_sha256"], row["category"], row["related_source_id"], row["note"], json.dumps(row["evidence"]), owner.subject_id)
                    await platform.repo.audit(conn, owner.subject_id, "knowledge.source.classified", row["source_id"], {"disposition_id": identifier, "category": row["category"]})
                    await platform.repo.remember(conn, owner.subject_id, key, fingerprint, {"id": identifier})
        retain(SCOPE / "source-dispositions-03.json", record)
    finally: await pool.close()


if __name__ == "__main__": activate(); asyncio.run(classify())
