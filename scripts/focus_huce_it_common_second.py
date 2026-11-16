"""Record the user's IT/common scope and defer other programme documents."""
from collections import Counter
from datetime import UTC, datetime

from knowledge_platform import ROOT
from continue_huce_completion_20261025 import CORPUS, OUT, checked, read, save, sha
from review_huce_construction_economics_english_second import SOURCE as KTE
from campus247.application.conversation.followup import normalized_question


def main():
    status = read(OUT / "source-status-06.json")
    curricula = {s["source_id"] for s in read(OUT / "curriculum-cell-candidates-01.json")["sources"]}
    rows = []
    for source in status["sources"]:
        title = normalized_question(source["title"])
        is_it = any(term in title for term in ("cong nghe thong tin", "khoa hoc may tinh", "khoa hoc du lieu",
            "tin hoc xay dung", "cntt", "fit cma", "an toan thong tin"))
        group = "CNTT" if is_it else "DE_SAU" if source["source_id"] in curricula else "DUNG_CHUNG"
        rows.append({"source_id": source["source_id"], "title": source["title"], "group": group,
            "execution_priority": "DEFERRED_BY_USER" if group == "DE_SAU" else "CURRENT_FOCUS",
            "reason": "Tài liệu ngành khác: để sau theo chỉ dẫn trực tiếp của người dùng" if group == "DE_SAU"
                else "Tài liệu CNTT/Tin học xây dựng/FIT hoặc an toàn thông tin" if group == "CNTT"
                else "Tài liệu và dịch vụ dùng chung cho sinh viên HUCE",
            "evidence_category_unchanged": source["category"], "serving_version_at_scope_change": source["serving_version"],
            "uri": source["uri"], "original_sha256": source["original_sha256"]})
    counts = dict(Counter(r["group"] for r in rows))
    assert len(rows) == 117 and counts == {"CNTT": 24, "DE_SAU": 71, "DUNG_CHUNG": 22}
    instruction = "tập trung vào tài liệu công nghệ thông tin và tài liệu chung thôi, còn các tài liệu khác đánh dấu là để sau"
    priority = {"at": datetime.now(UTC), "authority": "Direct human instruction in this conversation", "instruction": instruction,
        "source_status_reference": "source-status-06.json", "source_status_sha256": sha((OUT / "source-status-06.json").read_bytes()),
        "counts": counts, "focused_sources": 46, "deferred_sources": 71, "sources": rows,
        "meaning": "Execution priority only; preserve source contents, versions, existing serving membership, original evidence categories, authentication and provenance checks."}
    save(checked(OUT / "source-execution-priorities-01.json"), priority)
    by_id = {r["source_id"]: r for r in rows}
    limited = [s for s in status["sources"] if s["category"] in {"PARTIAL_SOURCE_TEXT", "SOURCE_SCOPE_UNRESOLVED"}]
    focused = [s for s in limited if by_id[s["source_id"]]["group"] != "DE_SAU"]
    deferred = [s for s in limited if by_id[s["source_id"]]["group"] == "DE_SAU"]
    save(checked(OUT / "remaining-evidence-worklist-focused-01.json"), {"at": datetime.now(UTC),
        "priority_manifest": "source-execution-priorities-01.json", "focused_remaining_sources": focused,
        "focused_remaining_count": len(focused), "deferred_sources": deferred, "deferred_count": len(deferred),
        "unresolved_focused_cohorts": sum(s["category"] == "SOURCE_SCOPE_UNRESOLVED" for s in focused),
        "focused_curriculum_sources": len(curricula - {r["source_id"] for r in rows if r["group"] == "DE_SAU"}),
        "all_focused_work_complete": False, "SSO_and_real_API_connected": False})
    document = checked(ROOT / "docs/HUCE_ACTIVE_DOCUMENT_SCOPE_20261025.md")
    lines = ["# Phạm vi tài liệu đang xử lý — CNTT và dùng chung", "",
        "Theo chỉ dẫn trực tiếp ngày25/10/2026: tập trung tài liệu công nghệ thông tin và tài liệu dùng chung; tài liệu ngành khác để sau.", "",
        "Danh mục hiện có117 nguồn: **24 CNTT,22 dùng chung,71 để sau**. Trong46 nguồn đang tập trung,22 nguồn còn giới hạn bằng chứng; sáu nguồn CNTT chưa xác định được khóa cụ thể. Việc đánh dấu ưu tiên giữ nguyên tài liệu, original, phiên bản và các kiểm soát nguồn/quyền đọc đã có.", "",
        "Tin học xây dựng, chương trình/hội nghị FIT, lịch CNTT và tài liệu an toàn thông tin thuộc nhóm đang xử lý. Học phí, quy chế, học bổng, ngoại ngữ, nhập học, rèn luyện, thư viện và Office365 thuộc tài liệu dùng chung.", "",
        "Bản bổ sung K71KTE đang chuẩn bị được để sau; không đưa thay đổi này vào bản phát hành tiếp theo. Bằng chứng và các ứng viên cũ vẫn được giữ.", ""]
    for group, label in (("CNTT", "CNTT — đang tập trung"), ("DUNG_CHUNG", "Dùng chung — đang tập trung"), ("DE_SAU", "Để sau — các ngành khác")):
        lines.extend([f"## {label}", "", "| Mã nguồn | Tài liệu | Trạng thái công việc |", "|---|---|---|"])
        for row in rows:
            if row["group"] == group:
                title = row["title"].replace("|", "\\|").replace("\n", " ")
                lines.append(f"| `{row['source_id'][:8]}` | {title} | {'Để sau' if group == 'DE_SAU' else 'Đang tập trung'} |")
        lines.append("")
    lines.extend(["Danh mục máy đọc và ID đầy đủ: `infra/local/huce-completion-20261025-02/source-execution-priorities-01.json`.", ""])
    with document.open("x", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    plan = read(CORPUS / "candidate-plan-31.json")
    baseline = next(e for e in read(CORPUS / "candidate-plan-25.json")["sources"] if e["source_id"] == KTE)
    assert sha(checked(ROOT / baseline["candidate"]).read_bytes()) == baseline["candidate_sha256"]
    plan["sources"] = [baseline if e["source_id"] == KTE else e for e in plan["sources"]]
    save(checked(CORPUS / "candidate-plan-32.json"), plan)
    print({"focused": 46, "remaining_focused": len(focused), "deferred": 71, "plan": "32", "KTE_addition_deferred": True})


if __name__ == "__main__":
    main()
