"""Two-phase HTTP check of local revocation durability; never prints credentials."""
import argparse
import json
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import httpx

from knowledge_platform import ROOT, STATE, checked_path, retain
from verify_knowledge_platform import API, BASE, login, require


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["before", "after"])
    parser.add_argument("--receipt")
    args = parser.parse_args()
    if args.phase == "before":
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
        receipt = checked_path(STATE / ("runtime-revocation-" + stamp + ".json"), ROOT)
        with closing(login("KA01")) as admin, closing(login("SV01")) as student:
            state = require(admin.get(API + "/state"))
            assert student.get(API + "/state").status_code == 403
            # An invalid release body is rejected by origin before application work.
            body = {"release_id": "00000000-0000-0000-0000-000000000001", "query": "origin check"}
            assert admin.post(API + "/search-preview", json=body,
                              headers={"Origin": "https://untrusted.invalid"}).status_code == 403
            assert admin.post(API + "/search-preview", json=body,
                              headers={"Origin": BASE}).status_code != 403
            token = admin.cookies.get("auth_token")
            assert token
            require(admin.post("/v1/auth/logout"))
            assert admin.get(API + "/state", headers={"Authorization": "Bearer " + token}).status_code == 401
            retain(receipt, {"token": token, "phase": "revoked", "release_id": state["desired"]["release_id"],
                             "generation": state["desired"]["generation"]})
        print(json.dumps({"receipt": str(receipt), "student_denied": True, "origin_guard": True, "logout": True}))
    else:
        if not args.receipt:
            raise ValueError("Exact task-owned receipt required")
        receipt = checked_path(Path(args.receipt), ROOT)
        if receipt.parent != STATE or not receipt.name.startswith("runtime-revocation-"):
            raise ValueError("Exact task-owned receipt required")
        value = json.loads(receipt.read_text(encoding="utf-8"))
        with httpx.Client(base_url=BASE, trust_env=False, timeout=30) as client:
            assert client.get(API + "/state", headers={"Authorization": "Bearer " + value["token"]}).status_code == 401
        with closing(login("KA02")) as admin:
            state = require(admin.get(API + "/state"))
            assert state["desired"]["release_id"] == value["release_id"]
            assert state["desired"]["generation"] == value["generation"]
        target = checked_path(receipt.with_name(receipt.stem + "-verified.json"), ROOT)
        retain(target, {"passed": True, "revoked_after_restart": True, "release_preserved": True,
                        "generation": value["generation"], "credentials_printed": False})
        print(json.dumps({"report": str(target), "passed": True}))


if __name__ == "__main__":
    main()
