"""Reproduce three visually reviewed K71 table-total excerpts; no generated evidence.

Full original PDFs and extracted pages remain immutable. Course relationships
and semester tables are deliberately pending structured visual review.
"""
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from huce_source_registry import ROOT, checked, save


def main():
    directory = checked(ROOT / "data/huce-discovery-20261020/curricula-20261020T150911234144Z")
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    reviewed = {
        "1nL31OteEeU7ZkRwIxwjrgP_hJO3MK6Ux": (
            "K71 — Kỹ sư Công nghệ thông tin / Công nghệ phần mềm — 71PM",
            "KẾ HOẠCH GIẢNG DẠY CHƯƠNG TRÌNH ĐÀO TẠO TRÌNH ĐỘ KỸ SƯ\n"
            "NGÀNH CÔNG NGHỆ THÔNG TIN/CHUYÊN SÂU: CÔNG NGHỆ PHẦN MỀM – 71PM\n"
            "Tổng: 180TC (Không tính HP giáo dục thể chất, Giáo dục quốc phòng)"),
        "1elVn8XX32jXyYo5eoHfznQ9PFLh01FmF": (
            "K71 — Công nghệ thông tin / Mạng máy tính và Truyền thông dữ liệu — 71MHT",
            "KẾ HOẠCH GIẢNG DẠY CHƯƠNG TRÌNH ĐÀO TẠO NGÀNH CÔNG NGHỆ THÔNG TIN\n"
            "CHUYÊN SÂU: MẠNG MÁY TÍNH VÀ TRUYỀN THÔNG DỮ LIỆU – 71MHT\n"
            "Tổng: 180TC (Không tính HP giáo dục thể chất, Giáo dục quốc phòng)"),
        "1hu58jGFk5Ue0gekWY-9WA-1wFnX7WklU": (
            "K71 — Kỹ sư Công nghệ thông tin / An toàn thông tin — 71IS",
            "KẾ HOẠCH GIẢNG DẠY CTĐT TRÌNH ĐỘ KỸ SƯ\n"
            "NGÀNH CÔNG NGHỆ THÔNG TIN/CHUYÊN NGÀNH AN TOÀN THÔNG TIN – 71IS\n"
            "Tổng: 180 TC (không tính HP Giáo dục thể chất và Giáo dục quốc phòng)"),
    }
    chunks = []
    for drive_id, (title, text) in reviewed.items():
        source = next(row for row in manifest["files"] if row["drive_id"] == drive_id)
        row = next(row for row in manifest["rows"] if row["drive_id"] == drive_id and row["scope"] == "K71")
        raw = checked(ROOT / source["original_file"])
        if hashlib.sha256(raw.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("original hash mismatch")
        chunks.append({"title": title, "url": row["publication_url"], "download_url": row["url"],
            "section": title + " — tiêu đề và dòng tổng tín chỉ, trang 1", "page": 1,
            "source_file": str(raw.relative_to(ROOT / "data")), "source_sha256": source["sha256"],
            "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "review_scope": "Title, program/cohort and total/exclusion footnote only; not course grid or prerequisite arrows",
            "academic_year": "2026-2027", "cohort": "K71", "effective_from": "2026-10-20T00:00:00+07:00",
            "effective_date_basis": "retrieval admission timestamp; not an inferred legal effective date",
            "published_at": None, "supersedes": [],
            "visual_evidence": str((directory / "visual-review" / (drive_id + ".png")).relative_to(ROOT))})
    output = checked(ROOT / "data/huce-public-20261013/reviewed-expansion-20261020.json")
    save(output, {"public_only": True, "acquired_at": datetime.now(UTC).isoformat(),
        "version_label": "reviewed-expansion-20261020", "verification": "visually_reviewed_source_excerpts",
        "extraction": "Verbatim title and total-row transcription after visual review; non-contiguous table excerpts, not a linearized course table.",
        "chunks": chunks})
    print(json.dumps({"manifest": str(output), "admitted_excerpts": len(chunks)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
