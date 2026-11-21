"""Does an uploaded file really go through the malware scanner? Run against the live runtime started WITH the scanner.

    python scripts/qa/scan_check.py [--base http://127.0.0.1:8015]

1. a harmless text file is accepted (202) and the document is then rejected again, so nothing stays in review;
2. the standard EICAR antivirus test string is refused. It is built in memory from pieces and sent from this process: it is never written
   to a disk (Windows Defender removes files containing it, which is why an earlier attempt ended at "scanner unavailable").
Exit code 1 when a check fails. Reads the owner's credentials from the runtime folder and never prints them.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
CREDENTIALS = ROOT / "infra/local/knowledge-platform-20261023/owner-credentials.json"
# The EICAR test string in three pieces (a harmless, industry-standard marker that every scanner reports as a test signature).
PIECES = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}$", "EICAR-STANDARD-ANTIVIRUS-", "TEST-FILE!$H+H*")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8015")
    args = parser.parse_args()
    creds = json.loads(CREDENTIALS.read_text(encoding="utf-8"))
    client = httpx.Client(base_url=args.base, headers={"Origin": args.base}, trust_env=False, timeout=120)
    login = client.post("/v1/knowledge/platform/session", json={"username": creds["username"], "password": creds["password"]})
    if login.status_code != 200:
        print("FAIL sign-in refused")
        return 1
    failures = []

    def check(ok: bool, message: str) -> None:
        print("ok  " if ok else "FAIL", message)
        if not ok:
            failures.append(message)

    def upload(name: str, body: bytes, title: str):
        metadata = {"title": title, "owner_unit": "QA", "canonical_uri": f"https://qa.huce.edu.vn/scan-check-{uuid.uuid4().hex[:10]}",
                    "programs": ["PUBLIC"], "audiences": ["STUDENT", "KNOWLEDGE_ADMIN", "SYSTEM_ADMIN"], "effective_from": None}
        return client.post("/v1/knowledge/platform/documents", headers={"Idempotency-Key": str(uuid.uuid4())},
                           data={"metadata": json.dumps(metadata)}, files={"file": (name, body, "text/plain")})

    clean = upload("qa-clean.txt", "QA kiểm tra quét virus: tệp văn bản sạch.\n".encode("utf-8"), "QA-scan-check sạch")
    check(clean.status_code == 202, f"a clean text file is accepted (HTTP {clean.status_code})")
    if clean.status_code == 202:
        version = clean.json().get("version_id")
        listing = client.get("/v1/knowledge/platform/documents").json().get("items", [])
        mine = next((r for r in listing if r["version_id"] == version), None)
        check(mine is not None, "the accepted file is listed")
        if mine and mine.get("can_reject"):
            done = client.post(f"/v1/knowledge/platform/documents/{version}/reject", json={"note": "QA scan check finished"})
            check(done.status_code == 200, f"the clean test document is rejected again (HTTP {done.status_code})")
    infected = upload("qa-infected.txt", "".join(PIECES).encode("ascii"), "QA-scan-check nhiễm")
    detail = infected.text[:160].replace("\n", " ")
    check(infected.status_code >= 400, f"the EICAR test string is refused (HTTP {infected.status_code}: {detail})")
    check(infected.status_code != 202, "the infected file is not accepted for review")
    print(f"{len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
