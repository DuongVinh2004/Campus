"""Build authored Vietnamese FAQs with immutable local official-source bindings.

This exports content, not a claim that the live chatbot answered every question.
No provider calls, database writes or replacement of source documents occur.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data/huce-faq-20261013"
SOURCES = ROOT / "data/huce-public-20261013"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def key(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold()).replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in text if unicodedata.category(c) != "Mn")).strip()


def build() -> None:
    for path in (DEST, SOURCES):
        if not path.resolve().is_relative_to(ROOT) or path.is_symlink():
            raise ValueError("Workspace-local ordinary directories required")
    manifests = {
        "H": json.loads((SOURCES / "handbook-reviewed.json").read_text(encoding="utf-8")),
        "R": json.loads((SOURCES / "regulations-ocr.json").read_text(encoding="utf-8")),
    }
    evidence, entries, seen = {}, [], set()
    for line in (DEST / "questions.tsv").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        topic, refs, question, answer = line.split("\t")
        normalized = key(question)
        if normalized in seen or not question.endswith("?") or len(answer) < 15:
            raise ValueError(f"Duplicate or malformed FAQ: {question}")
        if re.search(r"SYN-|CIT-|mô phỏng|fixture", question + answer, re.I):
            raise ValueError("Technical test artifacts cannot appear in FAQ content")
        seen.add(normalized)
        bindings = []
        for ref in refs.split(","):
            if ref == "L":
                manifest = manifests["H"]
                item = next(c for c in manifest["chunks"] if c.get("page") is None)
                name = "handbook-reviewed.json"
            else:
                match = re.fullmatch(r"([HR])(\d+)", ref)
                if not match:
                    raise ValueError(f"Invalid source reference: {ref}")
                kind, number = match.groups()
                manifest = manifests[kind]
                item = next(c for c in manifest["chunks"] if c.get("page") == int(number))
                name = "handbook-reviewed.json" if kind == "H" else "regulations-ocr.json"
            if manifest.get("public_only") is not True or not item["url"].startswith("https://"):
                raise ValueError("Verified public source required")
            evidence[ref] = {
                "title": item["title"], "url": item["url"], "download_url": item.get("download_url"),
                "pdf_page": item.get("page"), "section": item.get("section"),
                "source_manifest": f"../huce-public-20261013/{name}",
                "source_text_sha256": digest(item["text"]), "text": item["text"],
                "manifest_sha256": hashlib.sha256((SOURCES / name).read_bytes()).hexdigest(),
                "acquired_at": manifest["acquired_at"],
            }
            # Direct visual review resolved OCR inequality errors on these pages.
            image_path = {"H111": "handbook-pages/page-111.png",
                          "R16": "regulation-pages/page-16.png"}.get(ref)
            if image_path:
                evidence[ref]["visually_reviewed_pdf_page"] = {
                    "file": f"../huce-public-20261013/{image_path}",
                    "sha256": hashlib.sha256((SOURCES / image_path).read_bytes()).hexdigest(),
                    "note": "Đã đối chiếu ảnh trang gốc để xác nhận dấu ≥/≤ bị OCR đọc thiếu.",
                }
            bindings.append({"evidence_ref": ref, "url": item["url"], "pdf_page": item.get("page"),
                             "source_text_sha256": digest(item["text"])})
        entries.append({"number": len(entries) + 1, "topic": topic, "question": question,
                        "answer": answer, "sources": bindings,
                        "scope": "public_general_information", "live_chat_verified": False})
    if len(entries) < 300:
        raise ValueError(f"At least 300 independently authored FAQs required; got {len(entries)}")
    topics = dict(Counter(entry["topic"] for entry in entries))
    meta = {
        "title": "FAQ sinh viên HUCE", "language": "vi", "compiled_on": "2026-10-13",
        "entry_count": len(entries), "topics": topics,
        "source_policy": "Câu trả lời biên soạn từ nguồn HUCE; tài liệu gốc là căn cứ đối chiếu, FAQ không thay thế quyết định hay thông báo mới.",
        "regulation_scope": "Quy chế 1486/QĐ-ĐHXDHN ngày 06/11/2023: khóa tuyển sinh từ 2022 và tương đương. Trường hợp cá nhân cần đơn vị phụ trách xác nhận.",
        "page_convention": "Số trang là thứ tự trang PDF, tính từ 1, không phải số trang nội bộ của quy chế.",
        "validation_scope": "Kiểm tra cấu trúc, số lượng, trùng câu hỏi và tính toàn vẹn liên kết nguồn. Chưa chạy toàn bộ câu hỏi qua chatbot.",
        "runtime_note": "Quy tắc OutputGuard hiện tại còn chặn câu trả lời có từ kỷ luật; tạo bộ FAQ không sửa hay vô hiệu hóa quy tắc này.",
    }
    document = {**meta, "faqs": entries}
    lines = [f"# {len(entries)} câu hỏi thường gặp dành cho sinh viên HUCE", "", f"**{len(entries)} câu hỏi và câu trả lời**, chia thành {len(topics)} nhóm. Biên soạn ngày 13/10/2026.", "", meta["source_policy"], "", meta["regulation_scope"], "", meta["page_convention"], "", "## Các nhóm câu hỏi", ""]
    lines.extend(f"- {topic}: {count} câu" for topic, count in topics.items())
    previous = None
    for entry in entries:
        if entry["topic"] != previous:
            lines.extend(["", f"## {entry['topic']}", ""])
            previous = entry["topic"]
        lines.extend([f"### {entry['number']}. {entry['question']}", "", entry["answer"], ""])
        links = []
        for binding in entry["sources"]:
            item = evidence[binding["evidence_ref"]]
            label = "Hướng dẫn thư viện" if item["pdf_page"] is None else ("Sổ tay 2026–2027" if binding["evidence_ref"].startswith("H") else "Quy chế đào tạo 1486") + f", trang PDF {item['pdf_page']}"
            links.append(f"[{label}]({item['url']})")
        lines.append("Nguồn: " + "; ".join(links) + ".")
    lines.extend(["", "## Kiểm chứng và sử dụng", "", meta["validation_scope"], "", "Bản JSON chứa từng câu hỏi, câu trả lời và vị trí nguồn; evidence.json giữ đoạn nguồn cùng SHA-256 để kiểm tra. Khi đưa vào RAG, truy xuất và trích dẫn tài liệu HUCE gốc; không coi câu trả lời biên soạn là một văn bản quy định mới.", "", meta["runtime_note"], ""])
    outputs = {
        "faq.json": json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        "evidence.json": json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        "FAQ.md": "\n".join(lines),
        "validation.json": json.dumps({"entry_count": len(entries), "unique_questions": len(seen),
            "all_sources_resolved": True, "evidence_count": len(evidence), "topics": topics,
            "technical_test_markers_in_content": 0, "live_chat_verified_count": 0,
            "faq_content_sha256": digest(json.dumps(entries, ensure_ascii=False, sort_keys=True))}, ensure_ascii=False, indent=2) + "\n",
    }
    for name in outputs:
        path = DEST / name
        if path.exists() or not path.resolve().is_relative_to(ROOT):
            raise ValueError(f"Refusing replacement: {path}")
    for name, content in outputs.items():
        with (DEST / name).open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    print(json.dumps({"entries": len(entries), "topics": topics, "files": list(outputs)}, ensure_ascii=False))


if __name__ == "__main__":
    build()
