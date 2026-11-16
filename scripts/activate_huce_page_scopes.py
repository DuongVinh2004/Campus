"""Publish the exact three page-scope replacements using application confirmation."""
import asyncio
import json
import time
from contextlib import closing
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client
from complete_huce_corpus import SCOPE, actors, read
from knowledge_platform import TENANT, components, retain
from campus247.application.knowledge.platform_models import digest
from campus247.domain.shared.values import generate_uuid7


def activate():
    old = read(SCOPE / "candidate-release-04.json"); target = read(SCOPE / "candidate-release-05.json")
    probes = read(SCOPE / "page-scope-probes-02.json")
    assert probes["all_passed"] and probes["release_id"] == target["release_id"]
    previous = {row["source_id"]: row for row in old["members"]}
    members = {row["source_id"]: row for row in target["members"]}
    changed = {key for key in members if previous[key] != members[key]}
    assert changed == set(probes["changed_sources"]) and len(members) == 114
    with closing(client()) as c:
        before = c.get(API + "/state"); before.raise_for_status(); before = before.json()
        assert before["desired"]["release_id"] == old["release_id"] and before["desired"]["generation"] == 13
        response = c.post(API + "/previews", json={"operation": "activate", "target_id": target["release_id"], "expected_generation": 13})
        response.raise_for_status(); preview = response.json()
        assert preview["payload"]["target_sha256"] == target["membership_sha256"]
        assert {row["source_id"]: row for row in preview["payload"]["members"]} == members
        retain(SCOPE / "activation-preview-02.json", {key: value for key,value in preview.items() if key != "confirmation_token"})
        response = c.post(API + "/confirmations", headers={"Idempotency-Key": "huce-page-cohorts-20261024-activate-01"},
            json={"preview_id": preview["preview_id"], "confirmation_token": preview["confirmation_token"], "confirmed": True})
        response.raise_for_status(); retain(SCOPE / "activation-confirmation-02.json", response.json())
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            state = c.get(API + "/state").json(); availability = c.get(API + "/availability").json()
            if state["is_serving"] and state["desired"]["release_id"] == target["release_id"] and availability["generation"] == 14: break
            time.sleep(.5)
        else: raise RuntimeError("Runtime acknowledgement not verified")
        assert availability["serving_documents"] == 114 and availability["equivalent_sources"] == 3
        retain(SCOPE / "activation-ready-02.json", {"at": datetime.now(UTC).isoformat(), "desired": state["desired"],
            "serving": state["serving"], "availability": availability, "changed_sources": sorted(changed),
            "unchanged_members": 111, "source_page_scopes_verified": True})
        print(json.dumps({"release_id": target["release_id"], "generation": 14, "members": 114, "page_scopes_active": True}))


async def classify():
    previous = read(SCOPE / "source-dispositions-01.json"); plan = read(SCOPE / "candidate-plan-05.json")
    entries = {row["source_id"]: row for row in plan["sources"]}
    probes = read(SCOPE / "page-scope-probes-02.json"); changed = set(probes["changed_sources"])
    pool, _, platform, _ = await components(); _, owner = actors(); platform.admin(owner)
    try:
        for row in previous["sources"]:
            if row["source_id"] not in changed: continue
            candidate = read(SCOPE.parents[2] / entries[row["source_id"]]["candidate"])
            scope = candidate["applicability"]
            if scope.get("mixed_cohort_table"):
                row.update(category="SOURCE_SCOPE_UNRESOLVED", note="Bảng lịch học gộp nhiều khóa trên một trang; chưa xác minh ánh xạ từng hàng/cột. Chỉ tra cứu thông tin chung, chặn gán lịch theo một khóa cụ thể.")
            else:
                row.update(category="PARTIAL_SOURCE_TEXT", note="Đã tách phạm vi khóa theo từng trang có tiêu đề in rõ: " + ", ".join(scope["cohorts"]) + ". Không gộp môn/tổng tín chỉ giữa các khóa; chưa xác minh đầy đủ ô học kỳ hoặc mũi tên.")
            row["evidence"] = {"plan": "candidate-plan-05.json", "candidate_sha256": entries[row["source_id"]]["candidate_sha256"],
                "applicability": scope, "page_scope_probes": "page-scope-probes-02.json", "university_approval_claimed": False}
            fingerprint = digest(row)
            async with platform.repo.transaction() as conn:
                key = "corpus-page-scope-disposition-20261024:" + row["source_id"]
                replay = await platform.repo.replay(conn, owner.subject_id, key, fingerprint)
                if not replay:
                    identifier = generate_uuid7()
                    await conn.execute("""INSERT INTO knowledge_source_disposition(id,tenant_id,source_id,original_sha256,category,
                        related_source_id,note,evidence,created_by) VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9)""", identifier,
                        TENANT, row["source_id"], row["original_sha256"], row["category"], row["related_source_id"], row["note"], json.dumps(row["evidence"]), owner.subject_id)
                    await platform.repo.audit(conn, owner.subject_id, "knowledge.source.classified", row["source_id"], {"disposition_id": identifier, "category": row["category"]})
                    await platform.repo.remember(conn, owner.subject_id, key, fingerprint, {"id": identifier})
        retain(SCOPE / "source-dispositions-02.json", previous)
    finally: await pool.close()


if __name__ == "__main__":
    activate(); asyncio.run(classify())
