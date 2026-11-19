"""Enroll the local student account (`student-local`) in one synthetic learning class of the RUNNING runtime, through its own API.

    python scripts/learning_enroll_local_student.py [--base http://127.0.0.1:8015] [--offering-id UUID] [--apply]

Without --apply it only reports what it would do. It signs in as the synthetic learning admin (credentials read from the
learning workspace, never printed), looks for the class, and adds the student with the same preview-and-confirm steps a person
would use. Running it twice changes nothing the second time. To undo, archive that membership from the admin's class page.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
LEARNING_CREDENTIALS = ROOT / "infra/local/learning-materials-20261104-01/credentials.json"
STUDENT_IDENTITY = ROOT / "infra/local/knowledge-platform-20261023/student-identity.json"
STUDENT_CREDENTIALS = ROOT / "infra/local/knowledge-platform-20261023/student-credentials.json"


def login(base: str, username: str, password: str) -> httpx.Client:
    # The learning API refuses writes without this marker (the web client always sends it).
    client = httpx.Client(base_url=base, headers={"Origin": base, "X-Campus-Request": "learning"}, trust_env=False, timeout=30)
    reply = client.post("/v1/knowledge/platform/session", json={"username": username, "password": password})
    if reply.status_code != 200:
        raise SystemExit(f"sign-in refused for {username} (HTTP {reply.status_code})")
    return client


def pick_offering(client: httpx.Client, wanted: str | None) -> dict:
    rows = client.get("/v1/learning/admin/offerings").json()
    rows = rows["items"] if isinstance(rows, dict) else rows
    active = [row for row in rows if row.get("status") == "ACTIVE"]
    if wanted:
        active = [row for row in active if row["id"] == wanted]
    if not active:
        raise SystemExit("no active class to enroll the student in")
    return sorted(active, key=lambda row: row["id"])[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8015")
    parser.add_argument("--offering-id")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    accounts = {a["username"]: a for a in json.loads(LEARNING_CREDENTIALS.read_text(encoding="utf-8"))["accounts"]}
    admin = accounts["learning-admin"]
    student_subject = json.loads(STUDENT_IDENTITY.read_text(encoding="utf-8"))["subject_id"]
    client = login(args.base, admin["username"], admin["password"])
    offering = pick_offering(client, args.offering_id)
    members = client.get(f"/v1/learning/offerings/{offering['id']}/members").json()
    members = members["items"] if isinstance(members, dict) else members
    if any(m["actor_subject_id"] == student_subject and m["status"] == "ACTIVE" for m in members):
        print(json.dumps({"offering": offering["id"], "title": offering.get("title"), "already_enrolled": True}, ensure_ascii=False))
        return 0
    if not args.apply:
        print(json.dumps({"offering": offering["id"], "title": offering.get("title"), "would_enroll": True}, ensure_ascii=False))
        return 0
    payload = {"actor_subject_id": student_subject, "role": "STUDENT"}
    preview = client.post("/v1/learning/action-previews", json={"action": "member-create", "target_id": offering["id"], "payload": payload},
                          headers={"Idempotency-Key": str(uuid.uuid4())})
    preview.raise_for_status()
    token = {key: preview.json()[key] for key in ("preview_id", "confirmation_token")}
    done = client.post(f"/v1/learning/offerings/{offering['id']}/members", json=payload | token, headers={"Idempotency-Key": str(uuid.uuid4())})
    done.raise_for_status()
    student = json.loads(STUDENT_CREDENTIALS.read_text(encoding="utf-8"))
    seen = login(args.base, student["username"], student["password"]).get("/v1/learning/offerings").json()
    seen = seen["items"] if isinstance(seen, dict) else seen
    print(json.dumps({"offering": offering["id"], "title": offering.get("title"), "enrolled": True,
                      "student_sees_class": any(row["id"] == offering["id"] for row in seen)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
