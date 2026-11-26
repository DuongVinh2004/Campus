"""Write config/policy/gold/<rule>.json: scenarios authored from the regulation wording, not from the rule trees.

Expected answers are stated with plain integer arithmetic on the regulation's wording ("vượt quá 20%" means
absent * 100 > 20 * total, and so on), or as hand-listed literals. Each case carries a verbatim source span that
policy_rules_seed.src() cuts from the unit text. Authored by the model that also wrote the rules, so this is a
regression oracle, not a human-independent one; reported as such.
"""
from __future__ import annotations

import json
import sys
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from policy_rules_seed import ROOT, src  # noqa: E402

SAT, NOT, UND = "SATISFIED", "NOT_SATISFIED", "UNDETERMINED"
OUT = ROOT / "config" / "policy" / "gold"


def case(desc, inputs, expected, span):
    return {"description": desc, "inputs": inputs, "expected": expected, "source_span": {"unit_id": span["unit_id"], "quote": span["quote"]}}


def attendance():
    span = src("9cfbe01c0aca8f15", "nghỉ học không có lý do chính đáng vượt quá 20% thời lượng thiết kế")
    cases, seen = [], set()
    for total in (10, 15, 20, 30, 36, 45, 60, 90):
        thr = total // 5
        for absent in sorted({0, max(thr - 1, 0), thr, thr + 1, total}):
            key = (total, absent)
            if key in seen or absent > total:
                continue
            seen.add(key)
            exceeds = absent * 100 > 20 * total
            cases.append(case(f"Nghỉ không phép {absent}/{total} tiết", {"attendance.absent_periods": absent, "course.total_periods": total},
                NOT if exceeds else SAT, span))
    cases.append(case("Chỉ biết số tiết nghỉ, chưa biết tổng số tiết", {"attendance.absent_periods": 5}, UND, span))
    cases.append(case("Chỉ biết tổng số tiết", {"course.total_periods": 30}, UND, span))
    cases.append(case("Chưa nhập gì", {}, UND, span))
    return cases


def course_pass():
    span = src("686c639234150b83", "D: từ 4,0 đến 4,9")
    scores = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 3.7, 3.8, 3.9, 4.0, 4.1, 4.2, 4.5, 4.9, 5.0, 5.4, 5.5, 6.0, 6.4, 6.5, 6.9, 7.0, 7.5, 7.9,
              8.0, 8.4, 8.5, 9.0, 9.5, 10.0, 1.9, 2.9, 3.4, 3.6, 4.3, 4.6, 4.7, 4.8, 5.1, 5.2]
    cases = [case(f"Điểm học phần {s}", {"grade.course_score": s}, SAT if s >= 4.0 else NOT, span) for s in scores]
    cases.append(case("Chưa có điểm học phần", {}, UND, span))
    return cases


def warning():
    neutral = {"semester.failed_credits": 0, "semester.registered_credits": 20, "study.debt_credits": 0, "semester.is_first": False,
        "gpa.semester": 2.0, "student.year_level": 2, "gpa.cumulative": 2.0}
    w1 = src("95f6fc90ba169718", "vượt quá 50% khối lượng đã đăng kí học trong học kỳ")
    w1b = src("95f6fc90ba169718", "tổng số tín chỉ nợ đọng từ đầu khóa học vượt quá 24")
    w2f = src("7b32589e2489f185", "dưới 0,8 đối với học kỳ đầu của khóa học")
    w2n = src("7b32589e2489f185", "dưới 1,0 đối với các học kỳ tiếp theo")
    w3 = {1: src("3d08c940e5d91b6f", "dưới 1,2 đối với sinh viên trình độ năm thứ nhất"),
          2: src("3d08c940e5d91b6f", "dưới 1,4 đối với sinh viên trình độ năm thứ hai"),
          3: src("3d08c940e5d91b6f", "dưới 1,6 đối với sinh viên trình độ năm thứ ba"),
          4: src("3d08c940e5d91b6f", "dưới 1,8 đối với sinh viên các năm tiếp theo"),
          5: src("3d08c940e5d91b6f", "dưới 1,8 đối với sinh viên các năm tiếp theo")}
    cases = []
    for reg, failed in ((10, 5), (10, 6), (15, 7), (15, 8), (20, 10), (20, 11), (24, 12), (24, 13)):
        cases.append(case(f"Không đạt {failed}/{reg} tín chỉ trong học kỳ", {**neutral, "semester.failed_credits": failed, "semester.registered_credits": reg},
            SAT if failed * 100 > 50 * reg else NOT, w1))
    for debt in (0, 10, 23, 24, 25, 26, 40):
        cases.append(case(f"Nợ đọng {debt} tín chỉ", {**neutral, "study.debt_credits": debt}, SAT if debt > 24 else NOT, w1b))
    for g in (0.0, 0.5, 0.79, 0.8, 0.81, 0.9, 1.0):
        cases.append(case(f"Học kỳ đầu, điểm trung bình học kỳ {g}", {**neutral, "semester.is_first": True, "gpa.semester": g}, SAT if g < 0.8 else NOT, w2f))
    for g in (0.5, 0.99, 1.0, 1.01, 1.5):
        cases.append(case(f"Học kỳ sau, điểm trung bình học kỳ {g}", {**neutral, "gpa.semester": g}, SAT if g < 1.0 else NOT, w2n))
    limits = {1: 1.2, 2: 1.4, 3: 1.6, 4: 1.8, 5: 1.8}
    for year, lim in limits.items():
        for g in (round(lim - 0.01, 2), lim, round(lim + 0.2, 2)):
            cases.append(case(f"Năm {year}, điểm trung bình tích lũy {g}", {**neutral, "student.year_level": year, "gpa.cumulative": g}, SAT if g < lim else NOT, w3[year]))
    cases.append(case("Năm 2 với điểm tích lũy 1,3 (đạt năm 1 nhưng chưa đạt năm 2)", {**neutral, "student.year_level": 2, "gpa.cumulative": 1.3}, SAT, w3[2]))
    cases.append(case("Chưa nhập gì", {}, UND, w1))
    return cases


def withdrawal():
    s1 = src("7c96e982cc7d34f6", "vượt quá 2 lần liên tiếp")
    s2 = src("7c96e982cc7d34f6", "quá 4 lần không liên tiếp đối với chương trình đào tạo trình độ cử nhân")
    cases, seen = [], set()
    for kind in ("BACHELOR", "ENGINEER_SPECIAL"):
        for c in range(0, 5):
            for t in sorted({c, 4, 5, 6}):
                if t < c or (kind, c, t) in seen:
                    continue
                seen.add((kind, c, t))
                yes = c > 2 or (kind == "BACHELOR" and t > 4)
                cases.append(case(f"{'Cử nhân' if kind == 'BACHELOR' else 'Kỹ sư'}: {c} lần liên tiếp, tổng {t} lần cảnh báo",
                    {"program.kind": kind, "warnings.consecutive": c, "warnings.total": t}, SAT if yes else NOT, s1 if c > 2 or kind != "BACHELOR" else s2))
    cases.append(case("Không biết loại chương trình, 1 lần liên tiếp, tổng 5", {"warnings.consecutive": 1, "warnings.total": 5}, UND, s2))
    cases.append(case("Chưa nhập gì", {}, UND, s1))
    return cases


def graduation():
    cases = []
    s_complete = src("ca5f47f4f03daaed", "Tích lũy đủ học phần, số tín chỉ và hoàn thành các nội dung bắt buộc khác")
    s_gpa = src("6d5491f97471f4b0", "Điểm trung bình tích lũy của toàn khóa học đạt từ (2.0) trở lên")
    s_c = src("9346811296109432", "không bị truy cứu trách nhiệm hình sự")
    for complete, gpa, crim, disc in product((True, False), (1.99, 2.0, 2.01, 3.0), (False, True), ("NONE", "REPRIMAND", "WARNING", "SUSPENSION")):
        ok = complete and gpa >= 2.0 and not crim and disc != "SUSPENSION"
        span = s_complete if not complete else s_gpa if gpa < 2.0 else s_c
        cases.append(case(f"Đủ chương trình={complete}, điểm tích lũy {gpa}, truy cứu hình sự={crim}, kỷ luật {disc}",
            {"graduation.requirements_complete": complete, "gpa.cumulative": gpa, "criminal.liability": crim, "discipline.level": disc}, SAT if ok else NOT, span))
    cases.append(case("Chưa biết gì", {}, UND, s_gpa))
    return cases


def honors():
    s = src("fd009919541bf9cf", "vượt quá 5% so với tổng số tín chỉ quy định cho toàn chương trình")
    cases = []
    for gpa, (retake, total), disc in product((3.19, 3.2, 3.5, 3.6, 4.0), ((7, 150), (8, 150), (6, 120), (7, 120)), ("NONE", "REPRIMAND", "WARNING", "SUSPENSION")):
        exceeds = retake * 100 > 5 * total
        yes = gpa >= 3.2 and (exceeds or disc in ("WARNING", "SUSPENSION"))
        cases.append(case(f"Điểm tích lũy {gpa}, học lại {retake}/{total} tín chỉ, kỷ luật {disc}",
            {"gpa.cumulative": gpa, "retake.credits": retake, "program.total_credits": total, "discipline.level": disc}, SAT if yes else NOT, s))
    cases.append(case("Chưa nhập gì", {}, UND, s))
    return cases


GOLD = {"attendance-requirement": attendance, "course-pass": course_pass, "academic-warning": warning,
        "forced-withdrawal-warnings": withdrawal, "graduation-eligibility": graduation, "graduation-honors-demotion": honors}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for rule_id, make in GOLD.items():
        cases = make()
        (OUT / f"{rule_id}.json").write_text(json.dumps({"rule_id": rule_id, "authored_from": "regulation wording (units.jsonl)", "cases": cases},
            ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(rule_id, len(cases))
