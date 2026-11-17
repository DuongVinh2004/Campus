"""Retain new OCR revisions for two pages checked against their original images."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "data/huce-public-20261013"
REVIEWS = [
    ("handbook-reviewed.json", "handbook-human-reviewed.json", 111, "handbook-pages/page-111.png", {
        "> 2,5": "≥ 2,5",
    }),
    ("regulations-ocr.json", "regulations-human-reviewed.json", 16, "regulation-pages/page-16.png", {
        "M<\\NÑ <2M": "M ≤ N < 2M",
        "2M <N < 3M": "2M ≤ N < 3M",
        "3M <N <4M": "3M ≤ N < 4M",
        "4M <N < 5M": "4M ≤ N < 5M",
    }),
]

for original, revised, page, image, replacements in REVIEWS:
    target = DIRECTORY / revised
    if target.exists() or not target.resolve().is_relative_to(ROOT):
        raise ValueError(f"Fresh workspace-local revision required: {target}")
    document = json.loads((DIRECTORY / original).read_text(encoding="utf-8"))
    chunk = next(c for c in document["chunks"] if c["page"] == page)
    before = chunk["text"]
    for old, new in replacements.items():
        if old not in chunk["text"]:
            raise ValueError(f"Reviewed OCR text changed: {old}")
        chunk["text"] = chunk["text"].replace(old, new)
    document["human_review"] = {"original_manifest": original, "pdf_page": page,
        "image_file": image, "image_sha256": hashlib.sha256((DIRECTORY / image).read_bytes()).hexdigest(),
        "original_text_sha256": hashlib.sha256(before.encode()).hexdigest(),
        "corrected_text_sha256": hashlib.sha256(chunk["text"].encode()).hexdigest(),
        "corrections": replacements, "reason": "Đối chiếu ảnh PDF gốc: OCR đọc sai dấu bất đẳng thức."}
    with target.open("x", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2)
    print(revised, page)
