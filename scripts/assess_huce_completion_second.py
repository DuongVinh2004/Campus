"""Adjudicate one immutable live run; never merge passing cases across runs."""
import argparse
import re
from datetime import UTC, datetime

from continue_huce_completion_20261025 import CORPUS, OUT, ROOT, read, save, sha
from knowledge_platform import STATE
from report_huce_corpus_completion import TERMS as OLD_TERMS, CLARIFICATIONS, REFUSALS as OLD_REFUSALS, verdict
from report_huce_evidence_20261025 import TERMS as EXTRA_TERMS, REFUSALS as EXTRA_REFUSALS, assess_extra, source_checks
from campus247.application.conversation.followup import normalized_question

TERMS = {
    "reg_full_elective_continuation": ["kiến thức cần thiết", "tự chọn theo hướng dẫn", "tự chọn tuỳ ý"],
    "reg_full_hours": ["6 giờ 30 phút", "20 giờ 30 phút", "thứ Hai", "thứ Bẩy"],
    "reg_full_semester_weeks": ["15 tuần thực học", "3 tuần thi", "5 tuần thực học", "1 tuần thi"],
    "reg_full_registration_load": ["2/3", "3/2", "trung bình", "kế hoạch"],
    "reg_full_online_exception": ["30%", "thiên tai", "dịch bệnh", "Bộ Giáo dục"],
    "reg_full_letter_grades": ["B+", "8,0", "8,4", "C+", "6,5", "6,9", "D+", "5,0", "5,4", "P", "không tính"],
    "reg_full_improvement": ["không đạt", "lần học cuối", "đã có điểm học phần đạt", "cao nhất"],
    "reg_full_grade_conversion": ["B+", "3,5", "C+", "2,5", "D+", "1,5"],
    "reg_full_warning": ["dưới 0,8", "học kỳ đầu", "dưới 1,0", "học kỳ tiếp theo"],
    "reg_full_transfer_credit": ["50%", "khối lượng học tập tối thiểu"],
    "reg_full_downgrade_continuation": ["5%", "học lại", "cảnh cáo trở lên", "trong thời gian học"],
    "reg_full_personal_leave": ["01 học kỳ", "không thuộc", "buộc thôi học", "xem xét kỷ luật", "được tính", "thời gian học chính thức"],
    "reg_full_exchange": ["Hiệu trưởng", "hai trường đồng ý", "25%"],
    "reg_full_second_programme": ["năm thứ hai", "01 trong 02", "các điều kiện khác", "khá trở lên", "ngưỡng bảo đảm chất lượng", "trung bình", "điều kiện trúng tuyển"],
    "reg_full_applicability": ["2022", "tương đương"],
    "geo_semester_1": ["531800", "291802", "390111", "390121", "531802", "450101", "291801", "531805", "thể chất 1", "thể chất 2"],
    "geo_credit_531816": ["531816", "3", "Ngôn ngữ LT", "UD trong ĐPT"],
    "geo_elective_1": ["TỰ CHỌN 1 (2TC)", "531833", "Lập trình âm thanh", "531834", "Kỹ thuật âm thanh"],
    "geo_elective_2": ["TỰ CHỌN 2 (2TC)", "531835", "Marketing và truyền thông", "531836", "Thiết kế mỹ thuật CN"],
    "geo_prerequisite_game": ["531816", "→", "451802"],
    "geo_corequisite_vr": ["531829", "↔", "531830"],
    "km_semester1": ["280203", "428801", "390111", "300103", "940201", "390121", "240131", "240102", "thể chất 1", "1TC"],
    "km_code_268809": ["268809", "2", "Thực hành ký thuật", "cơ khí"],
    "km_pe_explicit": ["thể chất 2", "1TC"],
    "km_prereq": ["010213", "→", "010212"],
    "km_coreq": ["250102", "↔", "250103"],
    "mtc_semester1": ["988803", "940201", "250101", "250103", "390111", "390121", "240102", "240131", "510211", "thể chất 1"],
    "mtc_code_098802": ["098802", "3", "Các quá trình lý hóa", "kỹ thuật môi trường"],
    "mtc_elective": ["3TC", "088812", "118808", "108827"],
    "mtc_prereq_bent_waste": ["098802", "→", "098809"],
    "mtc_prereq_upward": ["158801", "→", "138806"],
    "mtc_prereq_bent_heat": ["250102", "→", "118805"],
    "mtc_coreq_air": ["108818", "↔", "108819"],
    "mtc_coreq_physics": ["250101", "↔", "250103"],
}
REFUSALS = {"reg_full_missing_appendix", "reg_full_personal_academic", "geo_wrong_cohort", "geo_wrong_semester",
    "geo_unproven_edge", "geo_unlabelled_pe_credit", "km_conflicting_cohort", "km_wrong_semester", "km_unprinted_link", "km_wrong_type",
    "mtc_wrong_cohort", "mtc_unprinted_edge", "mtc_unlabelled_pe", "mtc_elective_count", "mtc_placeholder_code",
    "econ_wrong_cohort", "econ_unprinted_group", "econ_unverified_semester", "econ_unverified_edge", "econ_unverified_count"}


def assess(case, receipt, release):
    memberships = {release["release_id"]: {m["source_id"]: m["version_id"] for m in release["members"]}}
    name = case["name"]
    if name in set(OLD_TERMS) | OLD_REFUSALS | CLARIFICATIONS:
        return verdict(case, receipt, memberships)
    if name in set(EXTRA_TERMS) | EXTRA_REFUSALS:
        return assess_extra(case, receipt, memberships[release["release_id"]])
    final = case.get("final") or {}; body = normalized_question(final.get("content", "")); failures = []
    if case["http_status"] != 200:
        failures.append("http")
    if name in REFUSALS:
        if final.get("status") != "abstained" or final.get("citations"):
            failures.append("expected_abstention_without_citations")
        if name == "reg_full_personal_academic" and "chua ket noi" not in body:
            failures.append("missing_personal_data_connection_disclosure")
    else:
        expected_terms = TERMS.get(name)
        expected_page = None
        if name.startswith("econ_p"):
            candidate = read(OUT / "economics-elective-columns-candidate-01.json")
            group = next(g for g in candidate["extracted"]["curriculum_geometry"]["elective_groups"] if "econ_"+g["id"] == name)
            expected_terms = [group["header"]["text"]] + [option["value"]["text"] for option in group["options"]]
            expected_page = group["page"]
        assert expected_terms is not None, name
        if final.get("status") != "answered":
            failures.append("required_answer_missing")
        missing = [term for term in expected_terms if normalized_question(term) not in body]
        if missing:
            failures.append({"missing_material_terms": missing})
        if not source_checks(case, receipt, memberships[release["release_id"]]):
            failures.append("source_hash_auth_release_binding")
        if expected_page and any(s["body"]["citation"]["locator"]["page_start"] != expected_page for s in case.get("sources", [])):
            failures.append("wrong_language_page")
        if name == "mtc_semester1" and re.search(r"(?:gd|giao duc)\s+the chat\s+1\s*[-–:(]*\s*\d+\s*(?:tc|tin chi)", body):
            failures.append("unprinted_pe_credit")
        if name == "geo_credit_531816" and any(term in body for term in ("lap trinh", "ung dung")):
            failures.append("unprinted_abbreviation_expansion")
    return {"name": name, "passed": not failures, "failures": failures, "status": final.get("status"),
        "latency_seconds": case["latency_seconds"], "conversation_id": case["conversation_id"]}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--receipt", required=True)
    parser.add_argument("--release", choices=["13", "14", "18"], required=True)
    parser.add_argument("--output", required=True); args = parser.parse_args()
    assert re.fullmatch(r"independent-questions-\d{8}T\d{12}\.json", args.receipt)
    assert re.fullmatch(r"live-verdict-(?:73|90|120)-\d{2}\.json", args.output)
    file = STATE / args.receipt; receipt = read(file); release = read(CORPUS / f"candidate-release-{args.release}.json")
    binding = receipt["state"]["desired"]
    assert binding["release_id"] == release["release_id"] and binding["generation"] == release["expected_generation"] + 1
    rows = [assess(case, receipt, release) for case in receipt["cases"]]
    expected_count = int(args.output.split("-")[2]); assert len(rows) == expected_count
    result = {"at": datetime.now(UTC), "receipt": str(file.relative_to(ROOT)), "receipt_sha256": sha(file.read_bytes()),
        "binding": binding, "count": len(rows), "passed": sum(r["passed"] for r in rows), "all_passed": all(r["passed"] for r in rows),
        "verdicts": rows, "throttle_events": len(receipt["throttles"]),
        "method": "One complete immutable API run; material conditions/units/rosters and immutable source hash/authentication/release bindings assessed; no cases substituted from another run",
        "entire_corpus_or_integration_complete": False}
    save(OUT / args.output, result)
    print({k: result[k] for k in ("count", "passed", "all_passed")})
    for row in rows:
        if not row["passed"]: print(row)


if __name__ == "__main__":
    main()
