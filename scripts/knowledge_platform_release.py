"""Publish only explicitly source-checked versions through the application workflow.

The approval note records automated technical review under the owner's direct
authorization. It never claims an independent university officer reviewed it.
"""
import json
from datetime import UTC, datetime

import httpx

from knowledge_platform import ROOT, STATE, TENANT, checked_path, retain
from campus247.infrastructure.identity.local_owner import LocalOwnerIdentityAdapter

BASE, API = "http://127.0.0.1:8015", "/v1/knowledge/platform"
TUITION = {"version_id": "e72d7b67-ba76-7d51-8a36-f21ea0630029",
    "original_sha256": "380b5140c32a3e05f8516663cf7ffbddcecfc7e2059fea259c1b8784379eb7fd",
    "effective_from": "2026-06-09T17:00:00Z",
    "basis": "QĐ 924/QĐ-ĐHXDHN, scan trang 1: ký ngày 10/06/2026, Điều 2: hiệu lực kể từ ngày ký; bảng trang 2 áp dụng năm học 2026-2027. Không suy ra ngày kết thúc năm học. HTML original và hai ảnh embedded đã khớp acquisition receipt SHA256; không dùng PDF dựng lại làm original."}


def checked(response, expected=200):
    if response.status_code != expected:
        raise RuntimeError(f"Application rejected operation: HTTP {response.status_code}: {response.text[:600]}")
    return response.json()


def run():
    adapter = LocalOwnerIdentityAdapter(checked_path(STATE / "owner-identity.json", ROOT), TENANT)
    directory = adapter.directory()
    creds = json.loads((STATE / "owner-credentials.json").read_text(encoding="utf-8"))
    with httpx.Client(base_url=BASE, trust_env=False, timeout=60) as author, httpx.Client(base_url=BASE, trust_env=False, timeout=60) as reviewer:
        author.headers["Authorization"] = "Bearer " + adapter.mint_token(directory["agent_id"])
        checked(reviewer.post(API + "/session", json={k: creds[k] for k in ("username", "password")}))
        state = checked(reviewer.get(API + "/state"))
        old = next(v for v in state["versions"] if v["version_id"] == TUITION["version_id"])
        if old["original_sha256"] != TUITION["original_sha256"] or old["revoked_at"]:
            raise ValueError("Reviewed source changed")
        raw = reviewer.get(API + f"/versions/{old['version_id']}/original")
        import hashlib
        if raw.status_code != 200 or hashlib.sha256(raw.content).hexdigest() != TUITION["original_sha256"]:
            raise ValueError("Original response mismatch")
        metadata = checked(author.post(API + f"/versions/{old['version_id']}/applicability-versions",
            json={"expected_revision":old["revision"], "effective_from":TUITION["effective_from"], "basis":TUITION["basis"]},
            headers={"Idempotency-Key":"tuition-924-source-bound-applicability-20261023"}),201)
        version_id = metadata["version_id"]
        current = checked(reviewer.get(API + "/state"))
        version = next(v for v in current["versions"] if v["version_id"] == version_id)
        note = ("Duyệt kỹ thuật TỰ ĐỘNG do agent thực hiện theo chỉ định tài khoản chịu trách nhiệm của chủ hệ thống ngày 23/10/2026; "
                "KHÔNG phải xác nhận của cán bộ HUCE. Đã xem hai scan QĐ 924; đối chiếu mọi mức tiền, khóa, CN/KS/KTS/ĐVHT và phụ thu; "
                "original/hash/HTML embedded và rendition đã kiểm tra. " + TUITION["basis"])
        if version["review_state"] != "APPROVED":
            checked(reviewer.post(API + f"/versions/{version_id}/reviews",
                json={"expected_revision":version["revision"],"verdict":"APPROVED","note":note}))
        release = checked(reviewer.post(API + f"/versions/{version_id}/releases",json={},
            headers={"Idempotency-Key":"tuition-924-real-release-20261023"}),201)
        preview = checked(reviewer.post(API + "/previews",json={"operation":"activate","target_id":release["release_id"],
            "expected_generation":release["expected_generation"]}))
        # Confirm exactly the reviewed membership; no fixture is retained.
        if {m["version_id"] for m in preview["payload"]["members"]} != {version_id}:
            raise ValueError("Unexpected release membership; no confirmation sent")
        result = checked(reviewer.post(API + "/confirmations", json={"preview_id":preview["preview_id"],
            "confirmation_token":preview["confirmation_token"],"confirmed":True},
            headers={"Idempotency-Key":"tuition-924-activate-20261023"}))
        receipt = {"source":TUITION,"metadata":metadata,"release":release,"preview":preview["payload"],"result":result,
            "review_note":note,"human_university_approval_claimed":False,"new_model_calls":0}
        path=STATE/("real-release-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".json")
        retain(path,receipt)
        print(json.dumps({"receipt":str(path),"release_id":release["release_id"],"version_id":version_id,"result":result},ensure_ascii=False))


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    run()
