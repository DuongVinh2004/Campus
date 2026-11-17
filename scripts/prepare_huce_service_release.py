"""One bounded, visually reviewed HTML service excerpt; originals stay immutable."""
import hashlib
import json
from datetime import UTC, datetime

from huce_source_registry import ROOT, checked, save

URL = "https://ttcntt.huce.edu.vn/huong-dan-tai-office-365-bang-tai-khoan-microsoft-office-365-duoc-nha-truong-cung-cap"
OUTPUT = ROOT / ".tooling/huce-continuation-20261020-01"


def main():
    registry = json.loads(checked(ROOT / "data/huce-discovery-20261020/run-20261020T152333749632Z/registry.json").read_text(encoding="utf-8"))
    source = next(row for row in registry if row["url"] == URL)
    original = checked(ROOT / source["original_file"])
    assert hashlib.sha256(original.read_bytes()).hexdigest() == source["sha256"]
    text = json.loads(checked(ROOT / source["text_file"]).read_text(encoding="utf-8"))["text"]
    excerpt = text[text.index("Bước 1:"):text.index("\nPrevious Post")]
    assert all(f"Bước {n}:" in excerpt for n in range(1, 5))
    assert "10 Feb, 2025" in text and "Install apps" in excerpt
    now = datetime.now(UTC).isoformat()
    item = {
        "url": URL, "download_url": URL, "title": source["title"],
        "issuer": "Trung tâm Công nghệ thông tin và Cơ sở dữ liệu — HUCE",
        "section": "Hướng dẫn tải Office 365 — Bước 1–4 (tài khoản đã được trường cung cấp)",
        "source_file": str(original.relative_to(ROOT / "data")),
        "source_sha256": source["sha256"], "text": excerpt,
        "text_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
        "published_at": "2025-02-10", "collected_at": source["collected_at"],
        "document_number": None, "legal_effective_from": None,
        "effective_from": now, "effective_date_basis": "retrieval admission, not legal effectiveness",
        "supersedes": [], "ocr_quality": "not_applicable_native_html",
        "review_status": "visually_reviewed_text",
        "review_scope": "All four textual installation steps and publication date; images unavailable",
        "applicability": {"audience": "holders of an already supplied university Microsoft Office 365 account",
                          "cohort": None, "programme": None, "academic_year": None, "system": None},
        "limitations": ["Illustrations failed to load during review", "No account issuance or password reset procedure supplied",
                        "No cohort, academic year, entitlement period or legal effectiveness stated"],
        "visual_evidence": ".tooling/huce-continuation-20261020-01/office-steps.png",
    }
    release = {"public_only": True, "acquired_at": now, "version_label": "reviewed-services-20261020-01",
               "verification": "visually_reviewed_source_excerpts", "chunks": [item]}
    save(ROOT / "data/huce-public-20261013/reviewed-services-20261020-01.json", release)
    save(OUTPUT / "source-registry.json", {"baseline_registry": "data/huce-discovery-20261020/run-20261020T152333749632Z/registry.json",
         "scope": "incremental service review; not a replacement of the full registry", "sources": [item]})
    print(json.dumps({"reviewed": 1, "new_downloads": 0, "output": str(OUTPUT)}))


if __name__ == "__main__":
    main()
