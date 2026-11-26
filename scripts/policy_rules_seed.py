"""Build config/policy/rules/*.json from the rag_v2 units and verify every quote verbatim.

The rules below were authored from the published training regulation (units.jsonl, family quy_che).
Every `quote` is cut from the unit text by this script (whitespace-insensitive match, then the real
substring is stored), so the stored quote is always a verbatim substring. Run with --check to
re-verify without writing.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api" / "src"))
from campus247.domain.policy_rules.rule import structural_issues, verbatim_issues  # noqa: E402
from campus247.domain.policy_rules.variables import load_vocabulary  # noqa: E402

MARK = "⟦RAG_V2_SOURCE⟧"
UNITS = {}
for line in (ROOT / "data" / "rag_v2_index" / "units.jsonl").read_text(encoding="utf-8").splitlines():
    u = json.loads(line)
    t = u["text"]
    i = t.find(MARK)
    u["body"] = t[i + len(MARK):].strip() if i >= 0 else t
    UNITS[u["unit_id"]] = u


def src(unit_id, fragment):
    u = UNITS[unit_id]
    pat = r"\s+".join(re.escape(w) for w in fragment.split())
    m = re.search(pat, u["body"])
    if not m:
        raise SystemExit(f"fragment not found in {unit_id}: {fragment}")
    path = re.sub(r" > tr\.\d+", "", u["path"])
    return {"unit_id": unit_id, "version_id": u["version_id"], "path": path, "quote": m.group(0)}


def pred(nid, var, op, value, unit, source):
    p = {"var": var, "op": op, "value": value}
    if unit:
        p["unit"] = unit
    return {"id": nid, "pred": p, "source": source}


def rule(rule_id, topic, code, label, concl_src, when, desc):
    return {"rule_id": rule_id, "topic": topic, "version": 1, "description": desc,
        "conclusion": {"code": code, "label": label, "source": concl_src},
        "applies": {"audiences": ["STUDENT"], "cohorts": {"from": None, "to": None}, "programs": ["*"],
            "effective": {"from": None, "to": None}},
        "when": when, "exceptions": [], "supersedes": [],
        "on_undetermined": {"refer_to": "ACADEMIC_SERVICES", "service_kind": "GENERAL_SUPPORT"},
        "graph_refs": []}


RULES = []

a3 = "9cfbe01c0aca8f15"
RULES.append(rule("attendance-requirement", "ATTENDANCE_REQUIREMENT", "NO_ATTENDANCE_F",
    "Không bị điểm F do nghỉ học quá mức cho phép",
    src(a3, "Sinh viên nghỉ học không có lý do chính đáng vượt quá 20% thời lượng thiết kế của học phần nào sẽ nhận điểm F"),
    {"id": "g", "all": [{"id": "n1", "not": pred("c1", "attendance.absent_ratio", ">", 20, "percent",
        src(a3, "nghỉ học không có lý do chính đáng vượt quá 20% thời lượng thiết kế"))}]},
    "Nghỉ không có lý do chính đáng quá 20% thời lượng của học phần thì nhận điểm F cho học phần đó."))

RULES.append(rule("course-pass", "COURSE_PASS", "PASSED",
    "Đạt học phần (điểm học phần từ 4,0 trở lên)",
    src("686c639234150b83", "Loại đạt có phân mức"),
    {"id": "g", "all": [pred("c1", "grade.course_score", ">=", 4, "point10",
        src("686c639234150b83", "D: từ 4,0 đến 4,9")),
        {"id": "n1", "not": pred("c2", "grade.course_score", "<", 4, "point10", src("fb98af8dfc96cde4", "F: dưới 4,0"))}]},
    "Điểm học phần dưới 4,0 là loại không đạt (F); từ 4,0 trở lên là loại đạt."))

w1, w2, w3 = "95f6fc90ba169718", "7b32589e2489f185", "3d08c940e5d91b6f"
RULES.append(rule("academic-warning", "ACADEMIC_WARNING", "WARNED", "Bị cảnh báo học tập cuối học kỳ chính",
    src("0d49d56bb8f0ee45", "Cuối mỗi học kỳ chính, sinh viên được cảnh báo học tập"),
    {"id": "g", "any": [
        pred("c1", "semester.failed_credit_ratio", ">", 50, "percent", src(w1, "vượt quá 50% khối lượng đã đăng kí học trong học kỳ")),
        pred("c2", "study.debt_credits", ">", 24, "credit", src(w1, "tổng số tín chỉ nợ đọng từ đầu khóa học vượt quá 24")),
        {"id": "g3", "all": [
            pred("c3a", "semester.is_first", "=", True, None, src(w2, "dưới 0,8 đối với học kỳ đầu của khóa học")),
            pred("c3b", "gpa.semester", "<", 0.8, "point4", src(w2, "dưới 0,8 đối với học kỳ đầu của khóa học"))]},
        {"id": "g4", "all": [
            pred("c4a", "semester.is_first", "=", False, None, src(w2, "dưới 1,0 đối với các học kỳ tiếp theo")),
            pred("c4b", "gpa.semester", "<", 1.0, "point4", src(w2, "dưới 1,0 đối với các học kỳ tiếp theo"))]},
        {"id": "g5", "all": [
            pred("c5a", "student.year_level", "=", 1, None, src(w3, "dưới 1,2 đối với sinh viên trình độ năm thứ nhất")),
            pred("c5b", "gpa.cumulative", "<", 1.2, "point4", src(w3, "dưới 1,2 đối với sinh viên trình độ năm thứ nhất"))]},
        {"id": "g6", "all": [
            pred("c6a", "student.year_level", "=", 2, None, src(w3, "dưới 1,4 đối với sinh viên trình độ năm thứ hai")),
            pred("c6b", "gpa.cumulative", "<", 1.4, "point4", src(w3, "dưới 1,4 đối với sinh viên trình độ năm thứ hai"))]},
        {"id": "g7", "all": [
            pred("c7a", "student.year_level", "=", 3, None, src(w3, "dưới 1,6 đối với sinh viên trình độ năm thứ ba")),
            pred("c7b", "gpa.cumulative", "<", 1.6, "point4", src(w3, "dưới 1,6 đối với sinh viên trình độ năm thứ ba"))]},
        {"id": "g8", "all": [
            pred("c8a", "student.year_level", ">", 3, None, src(w3, "trình độ năm thứ ba, dưới 1,8 đối với sinh viên các năm tiếp theo")),
            pred("c8b", "gpa.cumulative", "<", 1.8, "point4", src(w3, "dưới 1,8 đối với sinh viên các năm tiếp theo"))]}]},
    "Cảnh báo học tập khi một trong các điều kiện về tín chỉ không đạt, nợ đọng, điểm trung bình học kỳ hoặc tích lũy xảy ra."))

f1 = "7c96e982cc7d34f6"
RULES.append(rule("forced-withdrawal-warnings", "FORCED_WITHDRAWAL_WARNINGS", "FORCED_WITHDRAWAL",
    "Thuộc diện buộc thôi học do số lần cảnh báo học tập",
    src("d377f9b41792e1c1", "Sinh viên bị buộc thôi học trong các trường hợp sau"),
    {"id": "g", "any": [
        pred("c1", "warnings.consecutive", ">", 2, None, src(f1, "vượt quá 2 lần liên tiếp")),
        {"id": "g2", "all": [
            pred("c2a", "program.kind", "=", "BACHELOR", None, src(f1, "quá 4 lần không liên tiếp đối với chương trình đào tạo trình độ cử nhân")),
            pred("c2b", "warnings.total", ">", 4, None, src(f1, "quá 4 lần không liên tiếp đối với chương trình đào tạo trình độ cử nhân"))]}]},
    "Buộc thôi học khi vượt quá 2 lần cảnh báo liên tiếp, hoặc quá 4 lần không liên tiếp (cử nhân)."))

g1 = "d2cb2e30724ca42e"
RULES.append(rule("graduation-eligibility", "GRADUATION_ELIGIBILITY", "ELIGIBLE_TO_GRADUATE",
    "Đủ điều kiện xét công nhận tốt nghiệp",
    src(g1, "Sinh viên được Trường xét và công nhận tốt nghiệp cử nhân, kỹ sư/kiến trúc sư khi có đủ các điều kiện sau"),
    {"id": "g", "all": [
        pred("c1", "graduation.requirements_complete", "=", True, None, src("ca5f47f4f03daaed", "Tích lũy đủ học phần, số tín chỉ và hoàn thành các nội dung bắt buộc khác")),
        pred("c2", "gpa.cumulative", ">=", 2, "point4", src("6d5491f97471f4b0", "Điểm trung bình tích lũy của toàn khóa học đạt từ (2.0) trở lên")),
        pred("c3", "criminal.liability", "=", False, None, src("9346811296109432", "không bị truy cứu trách nhiệm hình sự")),
        pred("c4", "discipline.level", "!=", "SUSPENSION", None, src("9346811296109432", "không đang trong thời gian bị kỷ luật ở mức đình chỉ học tập"))]},
    "Điều kiện cần để xét tốt nghiệp: đủ chương trình, điểm trung bình tích lũy từ 2,0, không bị truy cứu hình sự, không đang bị đình chỉ."))

h = "cab2f2d1c64f7edf"
RULES.append(rule("graduation-honors-demotion", "HONORS_DEMOTION", "HONORS_DEMOTED",
    "Hạng tốt nghiệp (xuất sắc, giỏi) bị giảm một mức",
    src(h, "hạng tốt nghiệp của sinh viên có điểm trung bình tích lũy loại xuất sắc và giỏi sẽ bị giảm đi một mức"),
    {"id": "g", "all": [
        pred("c0", "gpa.cumulative", ">=", 3.2, "point4", src("c7f069ea15ed0010", "Từ 3,2 đến cận 3,6: Giỏi")),
        {"id": "g1", "any": [
            pred("c1", "retake.credit_ratio", ">", 5, "percent", src("fd009919541bf9cf", "vượt quá 5% so với tổng số tín chỉ quy định cho toàn chương trình")),
            pred("c2", "discipline.level", "in", ["WARNING", "SUSPENSION"], None, src("8cc2eec0f7312ea9", "kỷ luật từ mức cảnh cáo trở lên"))]}]},
    "Hạng tốt nghiệp xuất sắc/giỏi giảm một mức nếu học lại quá 5% chương trình hoặc từng bị kỷ luật từ cảnh cáo."))


def main(write: bool):
    vocab = load_vocabulary(ROOT / "config" / "policy" / "variables.toml")
    out = ROOT / "config" / "policy" / "rules"
    out.mkdir(parents=True, exist_ok=True)
    bad = 0
    for r in RULES:
        issues = structural_issues(r, vocab) + verbatim_issues(r, lambda uid: UNITS[uid]["body"] if uid in UNITS else None)
        if issues:
            bad += 1
            print("ISSUES", r["rule_id"], issues)
        if write:
            (out / f"{r['rule_id']}.json").write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(RULES)} rules, {bad} with issues")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(write="--check" not in sys.argv))
