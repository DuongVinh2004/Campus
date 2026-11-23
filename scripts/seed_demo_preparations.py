"""Give simulated students a few saved drafts on the academic services page (/services), through the running API.

    python scripts/seed_demo_preparations.py

Each draft goes through preview + confirmation like a person would do it; the drafts are local only and never sent to
the university (the page says so). Runs once per batch (receipt in infra/local/seed-demo-2026hk1/preparations-receipt.json).
"""
from __future__ import annotations

import json
import random
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts")]
from demo import campus_2026hk1 as sem  # noqa: E402

BASE = "http://127.0.0.1:8015"
RECEIPT = ROOT / "infra/local/seed-demo-2026hk1/preparations-receipt.json"
CREDENTIALS = ROOT / "infra/local/knowledge-platform-20261023/campus-directory-credentials.json"


def form(rng: random.Random, class_code: str) -> dict:
    kind = rng.choice(["STUDENT_CERTIFICATE", "STUDENT_CERTIFICATE", "GRADE_APPEAL", "GENERAL_SUPPORT"])
    if kind == "STUDENT_CERTIFICATE":
        purpose, recipient = rng.choice(sem.CERT_PURPOSES)
        return {"kind": kind, "purpose": purpose, "recipient": recipient,
                "reason": f"Em cần giấy xác nhận đang học lớp {class_code} để {purpose.lower()}."}
    if kind == "GRADE_APPEAL":
        code = rng.choice(sorted({c for _, _, c, _ in sem.CLASSES[class_code][1]}))
        return {"kind": kind, "course": f"{sem.COURSES[code][0]} ({code})",
                "reason": f"Em định phúc khảo vì {rng.choice(sem.APPEAL_REASONS)}; đang chờ xem lại bài trước khi nộp."}
    topic, text = rng.choice(sem.GENERAL_TOPICS)
    return {"kind": kind, "purpose": topic, "reason": text}


def main() -> int:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8")) if RECEIPT.exists() else {"seed_batch": sem.BATCH, "saved": {}}
    rng = random.Random(2011)
    students = [a for a in json.loads(CREDENTIALS.read_text(encoding="utf-8"))["accounts"] if a["role"] == "STUDENT"]
    for student in students:
        wanted = rng.choice([0, 0, 1, 1, 2])
        if student["username"] in receipt["saved"] or wanted == 0:
            continue
        client = httpx.Client(base_url=BASE, trust_env=False, timeout=30, headers={"Origin": BASE})
        client.post("/v1/knowledge/platform/session", json={"username": student["username"], "password": student["password"]}).raise_for_status()
        ids = []
        for _ in range(wanted):
            preview = client.post("/v1/student-preparations/preview", json={"form": form(rng, student["class_code"])})
            preview.raise_for_status()
            value = preview.json()
            saved = client.post("/v1/student-preparations/save", json={"preview_id": value["preview_id"],
                                "confirmation_token": value["confirmation_token"], "client_id": str(uuid.uuid4()), "confirmed": True})
            saved.raise_for_status()
            ids.append(saved.json().get("id"))
        receipt["saved"][student["username"]] = ids
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"students_with_drafts": len(receipt["saved"]), "drafts": sum(len(v) for v in receipt["saved"].values())}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
