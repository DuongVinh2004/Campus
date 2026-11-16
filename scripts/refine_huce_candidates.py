"""Refine source scopes and reject editorial placeholders; retain prior versions."""
import asyncio
import json
import re
from datetime import UTC, datetime

from complete_huce_corpus import SCOPE, read, windows
from knowledge_platform import ROOT, checked_path, components, retain
from campus247.application.knowledge.platform_models import digest
from campus247.application.knowledge.source_snapshot import validate_snapshot


async def main():
    plan = read(SCOPE / "candidate-plan-03.json")
    folder = checked_path(SCOPE / "candidates-refined-01", ROOT); folder.mkdir(exist_ok=False)
    changed = []
    for entry in plan["sources"]:
        if entry["status"] != "PREPARED": continue
        candidate = read(ROOT / entry["candidate"])
        texts = "\n".join(block["text"] for block in candidate["extracted"]["blocks"])
        if "[Nội dung bài là tệp đính kèm trong iframe; xem nguồn PDF liên kết.]" in texts:
            related = {"40b73b7c-f25b-7dc4-83cd-7dffe0524803": "39a92ade-e644-717e-8dbf-f33a8331fcc4",
                "a412a02b-ba07-7b94-8898-e38f0fbe1274": "ebb76b26-f8ea-766a-8c79-199d8f81dff6"}[entry["source_id"]]
            entry.update(status="LINKED_SOURCE_ALIAS", related_source_id=related,
                reason="Trang công bố dùng iframe; đoạn biên tập không phải bằng chứng. Phục vụ PDF đính kèm đã nhập ở nguồn liên quan; giữ nguyên trang và lịch sử.")
            changed.append(entry["source_id"]); continue
        scope = candidate["applicability"]
        edited = False
        if scope["kind"] == "COHORT_SNAPSHOT":
            # Explicit Kxx programme codes in the source are cohort witnesses;
            # a discovery label such as K70_and_earlier supplies no authority.
            cohorts = sorted(set("K" + value for value in re.findall(r"\bK\s*(\d{2})(?=[A-Z]|\b)", texts)))
            codes = sorted(set(re.findall(r"\bK?((?:6\d|7[01])[A-Z][A-Z0-9]{1,9})\b", texts)))
            cohorts = sorted(set(scope["cohorts"]) | set(cohorts))
            if cohorts != scope["cohorts"] or codes != scope["programme_codes"]:
                scope.update(cohorts=cohorts, programme_codes=codes); edited = True
        if entry["source_id"] == "129ba0a6-652e-70b8-8532-8e63661262ce":
            jobs = read(SCOPE / "stem-visual-01/jobs.json")
            pages = []
            for n in (1, 2):
                matches = list((SCOPE / "stem-visual-01").glob(f"page-{n}-*.json")); assert len(matches) == 1
                ocr = read(matches[0]); job = jobs["pages"][n-1]
                assert digest(checked_path(ROOT / job["image"], ROOT).read_bytes()) == ocr["image_sha256"]
                text = ocr["text"]
                if n == 1:
                    text = text[text.index("1. Đối tượng tham gia:"):].replace("Có ý chí phấn đầu", "Có ý chí phấn đấu").replace("Bản sao số hộ nghèo", "Bản sao sổ hộ nghèo")
                    text = "Thông báo 46/TB-ĐHXDHN-CTSV ngày 30 tháng 01 năm 2026\nVề Chương trình học bổng STEM Quỹ Châu Á năm học 2025-2026\n" + text
                else:
                    text = text[:text.index("Phòng Công tác Chính trị và Quản lý sinh viên thông báo")]
                pages.append({"block_id": str(n-1), "page": n, "text": text})
            candidate["extracted"] = {"original_sha256": candidate["original_sha256"], "blocks": pages,
                "review_witness": {"extractor": "agent-visual-selected-notice-clauses-v1", "images": jobs["pages"][:2],
                    "limitations": ["Selected clauses 1–6 from inspected pages 1–2; four blank application/CV template pages not transcribed"]}}
            candidate["pages"] = []
            for block in pages:
                for start, end in windows(block["text"]):
                    text = block["text"][start:end]
                    candidate["pages"].append({"block_id": block["block_id"], "page": block["page"], "text": text,
                        "char_start": start, "char_end": end, "text_sha256": digest(text.encode()), "section": entry["title"] + " · 2025-2026"})
            scope.update(academic_years=["2025-2026"], requires_academic_year=True,
                limitations=["Selected clauses 1–6 on pages 1–2; application templates on pages 3–6 not transcribed"])
            edited = True
        if not edited: continue
        scope["reviewed_at"] = datetime.now(UTC).isoformat()
        validate_snapshot(candidate, candidate["extracted"], original_sha256=candidate["original_sha256"],
            effective_from=datetime.fromisoformat(scope.get("legal_effective_from") or scope["reviewed_at"]))
        path = checked_path(folder / (entry["source_id"] + ".json"), ROOT); retain(path, candidate)
        entry.update(candidate=str(path.relative_to(ROOT)), candidate_sha256=digest(path.read_bytes()), cohorts=scope["cohorts"], parents=len(candidate["pages"]))
        changed.append(entry["source_id"])
    retain(SCOPE / "candidate-plan-04.json", plan)
    print(json.dumps({"refined": len(changed), "sources": changed}))


if __name__ == "__main__":
    asyncio.run(main())
