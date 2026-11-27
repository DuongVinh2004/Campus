"""Submit the owner-approved public CTSV notices (downloaded 2026-11-21) as the demo contributor `ctv.demo01`.

    python scripts/seed_demo_knowledge_queue.py

A contributor's document needs one approval by someone else before it can be published; this script only submits.
Files are real public HUCE notices (ctsv.huce.edu.vn), not simulated. Receipt: infra/local/seed-demo-2026hk1/knowledge-receipt.json.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8015"
FILES = ROOT / ".tooling/huce-ctsv-docs-20261121"
CREDENTIALS = ROOT / "infra/local/knowledge-platform-20261023/contributor-ctv.demo01-credentials.json"
RECEIPT = ROOT / "infra/local/seed-demo-2026hk1/knowledge-receipt.json"
UNIT = "Phòng Công tác Chính trị và Quản lý sinh viên"
PAGE = "https://ctsv.huce.edu.vn/"
DOCUMENTS = [
    ("doc-1.pdf", "Thông báo xét, cấp học bổng khuyến khích học tập cho sinh viên học kỳ II năm học 2025-2026",
     PAGE + "thong-bao-ve-viec-xet-cap-hoc-bong-khuyen-khich-hoc-tap-cho-sinh-vien-hoc-ky-ii-nam-hoc-2025-2026", "2026-10-20T00:00:00+07:00"),
    ("doc-2.pdf", "Thông báo mở đợt cập nhật thông tin sinh viên năm học 2025-2026",
     PAGE + "thong-bao-ve-viec-mo-dot-cap-nhat-thong-tin-sinh-vien-nam-hoc-2025-2026", "2026-05-14T00:00:00+07:00"),
    ("doc-3.pdf", "Thông báo triển khai đánh giá kết quả rèn luyện của sinh viên học kỳ I năm học 2025-2026",
     PAGE + "thong-bao-ve-viec-trien-khai-cong-tac-danh-gia-ket-qua-ren-luyen-cua-sinh-vien-hoc-ky-i-nam-hoc-2025-2026", "2026-01-28T00:00:00+07:00"),
    ("doc-4.pdf", "Thông báo tiếp nhận hồ sơ xét miễn, giảm học phí, hỗ trợ chi phí học tập, hỗ trợ học tập học kỳ II năm học 2025-2026",
     PAGE + "thong-bao-ve-viec-tiep-nhan-ho-so-xet-mien-giam-hoc-phi-ho-tro-chi-phi-hoc-tap-ho-tro-hoc-tap-hoc-ky-ii-nam-hoc-2025-2026", "2026-01-15T00:00:00+07:00"),
]


def main() -> int:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8")) if RECEIPT.exists() else {"submitted": {}}
    account = json.loads(CREDENTIALS.read_text(encoding="utf-8"))
    client = httpx.Client(base_url=BASE, trust_env=False, timeout=120, headers={"Origin": BASE})
    client.post("/v1/knowledge/platform/session", json={"username": account["username"], "password": account["password"]}).raise_for_status()
    for name, title, uri, effective in DOCUMENTS:
        if name in receipt["submitted"]:
            continue
        metadata = {"title": title, "owner_unit": UNIT, "canonical_uri": uri, "programs": ["PUBLIC"], "audiences": ["STUDENT"],
                    "effective_from": effective, "publish_directly": False, "attested": False}
        reply = client.post("/v1/knowledge/platform/documents", headers={"Idempotency-Key": str(uuid.uuid4())},
                            files={"file": (name, (FILES / name).read_bytes(), "application/pdf")},
                            data={"metadata": json.dumps(metadata, ensure_ascii=False)})
        receipt["submitted"][name] = {"status": reply.status_code, "body": reply.json() if reply.headers.get("content-type", "").startswith("application/json") else reply.text[:300]}
        RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding="utf-8")
        print(name, reply.status_code, json.dumps(receipt["submitted"][name]["body"], ensure_ascii=False)[:300])
    listing = client.get("/v1/knowledge/platform/documents").json()
    print(json.dumps(listing, ensure_ascii=False)[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
