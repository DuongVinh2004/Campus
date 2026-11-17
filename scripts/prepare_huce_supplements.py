"""Complete specifically reviewed exceptions without rewriting earlier candidates."""
import asyncio
import json
import re
from datetime import UTC, datetime
from html.parser import HTMLParser

from complete_huce_corpus import SCOPE, read, windows
from knowledge_platform import ROOT, checked_path, components, retain
from campus247.application.knowledge.platform_models import digest
from campus247.application.knowledge.source_snapshot import PROCESSOR, validate_snapshot

REGULATIONS = "253eb450-c57a-79a7-84a4-b0d85e12de1c"
MATERIALS = "dc43e7f5-466f-7ce3-8fe2-a10a0c809d9b"
ALIAS = "b14ed253-f075-789f-865a-28575a222e4b"
LIBRARY = "e417f8f1-8615-7d8c-8a75-f7a7cc3a83c9"
NOTICE = "c56e7a4c-b1c4-7a66-8132-24fe88db8ecc"

REGULATION_TEXT = """Số: 1486/QĐ-ĐHXDHN
Hà Nội, ngày 06 tháng 11 năm 2023
QUYẾT ĐỊNH
Về việc Ban hành Quy chế đào tạo trình độ đại học, chuyên sâu đặc thù bậc 7 của Trường Đại học Xây dựng Hà Nội
Điều 1. Ban hành kèm theo Quyết định này Quy chế đào tạo trình độ đại học, chuyên sâu đặc thù bậc 7 của Trường Đại học Xây dựng Hà Nội.
Điều 2. Quyết định này có hiệu lực thi hành từ ngày ký và thay thế cho Quyết định số 1053/QĐ-ĐHXDHN ngày 23 tháng 9 năm 2022 của Hiệu trưởng Trường Đại học Xây dựng Hà Nội về việc ban hành Quy chế đào tạo trình độ đại học.
Điều 3. Trưởng phòng Quản lý đào tạo, Trưởng các khoa, phòng, ban, bộ môn, sinh viên, các đơn vị và cá nhân liên quan chịu trách nhiệm thi hành Quyết định này."""

MATERIALS_TEXT = """TRƯỜNG ĐẠI HỌC XÂY DỰNG HÀ NỘI
KHOA VẬT LIỆU XÂY DỰNG
KẾ HOẠCH GIẢNG DẠY CHƯƠNG TRÌNH ĐÀO TẠO TRÌNH ĐỘ KỸ SƯ
NGÀNH CÔNG NGHỆ KỸ THUẬT VẬT LIỆU XÂY DỰNG (2025)
HK 1 (19TC)
HK 2 (19TC)
HK 3 (20TC)
HK 4 (19TC)
HK 5 (22TC)
HK 6 (23TC)
HK 7 (20TC)
HK 8 (20TC)
HK 9 (18TC)
Mã HP-X-Y
Tên học phần
X: Số tiết lý thuyết
Y: Số tiết hướng dẫn thực hành, thí nghiệm, chuyên đề đồ án
HP tiên quyết
HP song hành"""


class Body(HTMLParser):
    def __init__(self):
        super().__init__(); self.depth = 0; self.found = 0; self.parts = []; self.skip_depth = 0
    def handle_starttag(self, tag, attrs):
        if tag == "div":
            if self.depth: self.depth += 1
            elif {"single-blog-content", "content-layout1"} <= set(dict(attrs).get("class", "").split()):
                self.depth = 1; self.found += 1
            if self.depth and "post-navigation" in dict(attrs).get("class", "").split():
                self.skip_depth = self.depth
        if self.depth and not self.skip_depth and tag in {"p", "li", "br", "h1", "h2", "h3"}: self.parts.append("\n")
    def handle_endtag(self, tag):
        if self.depth and not self.skip_depth and tag in {"p", "li", "h1", "h2", "h3"}: self.parts.append("\n")
        if self.depth and tag == "div":
            if self.skip_depth == self.depth: self.skip_depth = 0
            self.depth -= 1
    def handle_data(self, data):
        if self.depth and not self.skip_depth: self.parts.append(data)
    def text(self):
        return "\n".join(line for value in "".join(self.parts).splitlines() if (line := " ".join(value.split())))


async def main():
    folder = checked_path(SCOPE / "candidates-supplement-03", ROOT); folder.mkdir(exist_ok=False)
    plan = read(SCOPE / "candidate-plan-01.json")
    inventory = read(SCOPE / "inventory-01.json")
    sources = {row["source_id"]: row for row in plan["sources"]}
    originals = {row["source_id"]: row for row in inventory["versions"]}
    pool, _, platform, _ = await components()
    try:
        specifications = []
        for identifier in ("44c96321-30ae-72aa-8453-182aacdb2bed", "5c0b7c32-2740-720a-87a5-3db734608d01"):
            previous = originals[identifier]
            async with pool.acquire() as conn:
                row = await platform.repo.version(conn, previous["version_id"])
                original = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1", row["original_id"])
            raw = platform.storage.read(original)
            parser = Body(); parser.feed(raw.decode("utf-8-sig"))
            if parser.found != 1 or len(parser.text()) < 100:
                raise ValueError("Unique original article body required")
            specifications.append((identifier, [{"page": None, "text": parser.text()}], "INFORMATION_SNAPSHOT",
                {"extractor": "single-blog-content-visible-paragraphs-v1", "original_sha256": previous["original_sha256"]}))
        specifications += [
            (REGULATIONS, [{"page": 1, "text": REGULATION_TEXT}], "LEGAL_EFFECT",
             {"extractor": "agent-visual-verbatim-selected-clauses-v1", "original_sha256": originals[REGULATIONS]["original_sha256"],
              "image": "infra/local/huce-corpus-completion-20261024-01/visual-review/regulation1486-page1.png",
              "image_sha256": "7849add61d5f7a009b390165d62e25d1a688799e1872bfd5f1de8f4d2f1bbe76",
              "limitations": ["Only decision header/date and Articles 1–3 on page 1; the 25-page regulation still requires clean OCR/verification"]}),
            (MATERIALS, [{"page": 1, "text": MATERIALS_TEXT}], "COHORT_SNAPSHOT",
             {"extractor": "agent-visual-selected-semester-totals-and-legend-v1", "original_sha256": originals[MATERIALS]["original_sha256"],
              "image": "infra/local/huce-corpus-completion-20261024-01/visual-review/materials2025-page1.png",
              "limitations": ["Printed 2025; no cohort inferred from the publication's mixed links", "Only header, semester totals and unit legend; no inferred overall total or course/arrow interpretation"]}),
        ]
        # A previously mislabeled discovery title is not cohort evidence.
        architecture = "8da40ef9-1850-7fa5-878d-86a2eb357674"
        prior = read(ROOT / sources[architecture]["candidate"])
        specifications.append((architecture, [{"page": b["page"], "text": b["text"]} for b in prior["extracted"]["blocks"]],
            "COHORT_SNAPSHOT", {"extractor": prior["extracted"]["extractor"], "original_sha256": prior["original_sha256"],
            "limitations": ["Printed 2025; do not assign to a cohort unless the source states it"]}))
        for identifier, pages, kind, witness in specifications:
            previous = originals[identifier]
            if witness.get("image"):
                image = checked_path(ROOT / witness["image"], ROOT)
                if witness.get("image_sha256") and digest(image.read_bytes()) != witness["image_sha256"]:
                    raise ValueError("Visual source changed")
                witness["image_sha256"] = digest(image.read_bytes())
            blocks = [{"block_id": str(i), **page} for i, page in enumerate(pages)]
            selections = []
            for block in blocks:
                for start, end in windows(block["text"]):
                    text = block["text"][start:end]
                    selections.append({"block_id": block["block_id"], "page": block["page"], "char_start": start, "char_end": end,
                        "text": text, "text_sha256": digest(text.encode()), "section": sources[identifier]["title"] + " · phạm vi đối chiếu đã ghi"})
            at = datetime.now(UTC).isoformat()
            applicability = {"kind": kind, "reviewed_at": at, "admission_only": kind != "LEGAL_EFFECT",
                "legal_effective_from": "2023-11-05T17:00:00+00:00" if kind == "LEGAL_EFFECT" else None,
                "cohorts": [], "programme_codes": [], "relations_verified": False,
                "limitations": witness.get("limitations", []), "effectivity_image_sha256": witness.get("image_sha256")}
            candidate = {**{k: sources[identifier][k] for k in ("source_id", "title", "uri")},
                "status": "PREPARED", "previous_version_id": previous["version_id"], "original_sha256": previous["original_sha256"],
                "processor": PROCESSOR, "issues": [], "applicability": applicability,
                "extracted": {"original_sha256": previous["original_sha256"], "blocks": blocks, "review_witness": witness}, "pages": selections}
            effective = datetime.fromisoformat(applicability["legal_effective_from"] or at)
            validate_snapshot(candidate, candidate["extracted"], original_sha256=candidate["original_sha256"], effective_from=effective)
            target = checked_path(folder / (identifier + ".json"), ROOT); retain(target, candidate)
            sources[identifier] = {**sources[identifier], "status": "PREPARED", "candidate": str(target.relative_to(ROOT)),
                "candidate_sha256": digest(target.read_bytes()), "kind": kind, "parents": len(selections), "cohorts": []}
        if originals[ALIAS]["original_sha256"] != originals[LIBRARY]["original_sha256"]:
            raise ValueError("Alias original differs")
        sources[ALIAS] = {**sources[ALIAS], "status": "EQUIVALENT_SOURCE_ALIAS", "related_source_id": LIBRARY,
            "reason": "Hai URI thư viện có cùng bytes bản gốc; dùng nguồn đã đối chiếu và giữ lịch sử URI còn lại."}
        plan["sources"] = [sources[row["source_id"]] for row in plan["sources"]]
        retain(SCOPE / "candidate-plan-02.json", plan)
        print(json.dumps({"supplement_candidates": len(specifications), "alias": ALIAS, "linked_scan_next": NOTICE}))
    finally:
        await pool.close()


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
