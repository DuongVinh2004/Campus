"""Keep form sections intact across embedding children and remove blank dot padding."""
import re
import argparse
from datetime import UTC, datetime

from knowledge_platform import ROOT
from continue_huce_completion_20261025 import CORPUS, OUT, read, save, sha
from prepare_huce_stem_full_second import STEM
from campus247.application.knowledge.source_snapshot import validate_snapshot


def main(base, number, attempt):
    plan = read(CORPUS / f"candidate-plan-{base}.json")
    entry = next(e for e in plan["sources"] if e["source_id"] == STEM)
    transcript_plan = read(CORPUS / "candidate-plan-15.json")
    transcript_entry = next(e for e in transcript_plan["sources"] if e["source_id"] == STEM)
    old_file = ROOT / transcript_entry["candidate"]
    assert sha(old_file.read_bytes()) == transcript_entry["candidate_sha256"]
    candidate = read(old_file); old = candidate["extracted"]["blocks"]
    previous = read(CORPUS / f"candidate-release-{base}.json")
    candidate["previous_version_id"] = next(m["version_id"] for m in previous["members"] if m["source_id"] == STEM)
    blocks = [{**b, "block_id": str(i)} for i, b in enumerate(old[:2])]
    bindings = []
    heading = "ĐƠN XIN CẤP HỌC BỔNG STEM QUỸ CHÂU Á"
    assert heading in old[2]["text"]
    def add(origin, fragment, section, *, title=None, compact=False):
        assert fragment in origin["text"]
        start = origin["text"].index(fragment)
        text = re.sub(r"\.{2,}", " ", fragment) if compact else fragment
        if title:
            assert title in origin["text"]
            text = title + "\n" + text
        block = {"block_id": str(len(blocks)), "page": origin["page"], "text": text,
            "section": f"STEM Quỹ Châu Á 2025–2026 — {section} — PDF {origin['page']}"}
        blocks.append(block)
        bindings.append({"new_block": block["block_id"], "old_block": origin["block_id"], "char_start": start,
            "char_end": start + len(fragment), "fragment_sha256": sha(fragment.encode()),
            "repeated_original_title": title, "blank_dot_padding_replaced_with_space": compact})
    form = old[2]; text = form["text"]
    markers = list(re.finditer(r"(?m)^[1-9]\. ", text))
    assert len(markers) == 9
    end_list = text.index("\n\nEm viết đơn này")
    add(form, text[:markers[0].start()].strip(), "Đơn xin — tiêu đề và lời hướng dẫn")
    i = 0
    while i < 9:
        # Keep the two consecutive motivation prompts together as printed;
        # each other numbered prompt remains a complete source paragraph.
        last = 7 if i == 6 else i
        end = markers[last+1].start() if last < 8 else end_list
        fragment = text[markers[i].start():end].strip()
        add(form, fragment, f"Đơn xin — gợi ý {i+1}–{last+1}", title=heading)
        i = last + 1
    commitment_end = text.index("Quyền lợi của sinh viên nhận học bổng")
    add(form, text[end_list:commitment_end].strip(), "Đơn xin — cam kết", title=heading)
    benefits_end = text.index("Nghĩa vụ của sinh viên nhận học bổng")
    add(form, text[commitment_end:benefits_end].strip(), "Đơn xin — quyền lợi", title=heading)
    activities_start = text.index("Các hoạt động của Chương trình trong năm học")
    add(form, text[benefits_end:activities_start].strip(), "Đơn xin — toàn bộ nghĩa vụ", title=heading)
    add(form, text[activities_start:], "Đơn xin — tiêu đề hoạt động tiếp ở PDF4")
    add(old[3], old[3]["text"], "Đơn xin — hoạt động, ký tên và lưu ý")
    add(old[4], old[4]["text"], "Sơ yếu lý lịch — toàn bộ nhãn trường trống", compact=True)
    family = old[5]; table_start = family["text"].index("Họ và tên những người đang chung sống với gia đình")
    add(family, family["text"][:table_start].strip(), "Sơ yếu lý lịch — thông tin cha mẹ", compact=True)
    add(family, family["text"][table_start:], "Sơ yếu lý lịch — bảng người chung sống và lời cam đoan", compact=True)
    at = datetime.now(UTC)
    review = {"at": at, "source_id": STEM, "original_sha256": candidate["original_sha256"],
        "previous_visual_review": "stem-six-page-review-01.json",
        "previous_visual_review_sha256": sha((OUT / "stem-six-page-review-01.json").read_bytes()),
        "previous_candidate": str(old_file.relative_to(ROOT)), "previous_candidate_sha256": sha(old_file.read_bytes()),
        "bindings": bindings, "method": "Complete numbered prompts/rights/obligations retained as parents; repeated headings are exact original headings; blank dot runs replaced with whitespace to preserve adjacent field-label separation, without filling any field",
        "university_approval_claimed": False, "serving_scope_expanded": False}
    target = OUT / f"stem-form-parent-review-{attempt}.json"; save(target, review)
    candidate["extracted"]["blocks"] = blocks
    candidate["extracted"]["review_witness"]["section_review"] = str(target.relative_to(ROOT))
    candidate["extracted"]["review_witness"]["section_review_sha256"] = sha(target.read_bytes())
    candidate["pages"] = [{"block_id": b["block_id"], "page": b["page"], "char_start": 0,
        "char_end": len(b["text"]), "text": b["text"], "text_sha256": sha(b["text"].encode()), "section": b["section"]} for b in blocks]
    candidate["applicability"]["reviewed_at"] = at.isoformat()
    validate_snapshot(candidate, candidate["extracted"], original_sha256=candidate["original_sha256"], effective_from=at)
    destination = OUT / f"stem-section-candidate-{attempt}.json"; save(destination, candidate)
    entry.update(candidate=str(destination.relative_to(ROOT)), candidate_sha256=sha(destination.read_bytes()), parents=len(blocks))
    save(CORPUS / f"candidate-plan-{number}.json", plan)
    print({"parents": len(blocks), "plan": number, "activated": False})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--attempt", required=True)
    args = parser.parse_args()
    assert all(re.fullmatch(r"\d{2}", v) for v in (args.base, args.plan, args.attempt))
    assert args.base != args.plan
    main(args.base, args.plan, args.attempt)
