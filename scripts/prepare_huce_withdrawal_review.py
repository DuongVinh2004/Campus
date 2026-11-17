"""Visually transcribe two separately numbered flows, correcting column-interleaved OCR."""
import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime

from huce_source_registry import ROOT, checked, save


def main():
    directory = ROOT / "data/huce-public-20261013"
    old = json.loads(checked(directory / "handbook-human-reviewed.json").read_text(encoding="utf-8"))
    prior = next(item for item in old["chunks"] if item.get("page") == 27)
    source = next(item for item in old["sources"] if item["file"] == "handbook-2026-2027.pdf")
    original = checked(directory / source["file"])
    assert hashlib.sha256(original.read_bytes()).hexdigest() == source["sha256"]
    evidence = checked(ROOT / ".tooling/huce-continuation-20261020-01/withdrawal-original.png")
    if not evidence.exists():
        renderer = shutil.which("pdftoppm")
        if not renderer:
            raise RuntimeError("Retained Poppler renderer required")
        subprocess.run([renderer, "-f", "27", "-l", "27", "-scale-to", "1700", "-singlefile", "-png",
                        str(original), str(evidence.with_suffix(""))], check=True)
    text = ("QUY TRÌNH HỦY ĐĂNG KÝ MÔN HỌC\n"
        "Bước 1: Phòng Quản lý Đào tạo thông báo điều kiện và thời gian để sinh viên rút bớt học phần đã đăng ký.\n"
        "Bước 2: Sinh viên gửi yêu cầu rút bớt học phần trên hệ thống quản lý đào tạo của Trường.\n"
        "Bước 3: Phòng quản lý đào tạo xử lý các yêu cầu rút bớt đăng ký của sinh viên.\n"
        "Bước 4: Phòng Quản lý Đào tạo thông báo kết quả rút bớt học phần và tổng học phí mới cho sinh viên sau khi đã rút học phần.\n\n"
        "QUY TRÌNH MỞ LỚP MÔN HỌC NGUYỆN VỌNG\n"
        "Bước 1: Phòng QLĐT ra thông báo về kế hoạch thu thập nguyện vọng để mở lớp.\n"
        "Bước 2: Sinh viên đăng ký nguyện vọng trên cổng thông tin sinh viên.\n"
        "Bước 3: Căn cứ vào số lượng nguyện vọng mở lớp, Phòng QLĐT sẽ mở và xếp TKB các lớp học lại.\n"
        "Bước 4: BM phân công giảng viên\nBước 5: Sinh viên đăng ký môn học\n"
        "Bước 6: GV thực hiện giảng dạy theo TKB đã sắp xếp")
    now = datetime.now(UTC).isoformat()
    reviewed = {"title": prior["title"], "url": prior["url"], "download_url": source["url"],
        "section": "Trang 27 — Quy trình hủy đăng ký môn học (4 bước); mở lớp môn học nguyện vọng (6 bước)",
        "page": 27, "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "source_file": str(original.relative_to(ROOT / "data")), "source_sha256": source["sha256"],
        "issuer": "Trường Đại học Xây dựng Hà Nội", "published_at": None, "collected_at": old["acquired_at"],
        "effective_from": now, "legal_effective_from": None, "document_number": None,
        "supersedes": [], "replaces_excerpt_text_sha256": hashlib.sha256(prior["text"].encode()).hexdigest(),
        "review_status": "visually_reviewed_numbered_flow_columns", "ocr_quality": "manual_visual_transcription_not_automated_ocr",
        "review_scope": "Page 27, both headings and each separately numbered step; column ownership kept intact",
        "applicability": {"cohort": None, "programme": None, "system": None, "academic_year": "2026-2027"},
        "limitations": ["Page says the training office announces deadlines; no exact deadline is stated here",
                        "No fee amount, refund entitlement or all-cohort rule inferred",
                        "Extraction correction, not a new institutional regulation"],
        "visual_evidence": str(evidence.relative_to(ROOT))}
    save(directory / "reviewed-withdrawal-20261021.json", {"public_only": True, "acquired_at": old["acquired_at"],
        "reviewed_at": now, "version_label": "reviewed-withdrawal-20261021",
        "verification": "visually_reviewed_source_excerpts", "chunks": [reviewed]})
    print(json.dumps({"reviewed_pages": 1, "numbered_flows": 2, "steps": 10, "original_preserved": True}))


if __name__ == "__main__":
    main()
