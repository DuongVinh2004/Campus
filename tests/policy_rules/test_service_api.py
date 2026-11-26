"""F2.3/F2.5: seed rules from the real regulation, public evaluation, authoring workflow, staleness, HTTP."""
from __future__ import annotations

import copy
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "announcements"))
from ann_helpers import NOW, person, sid  # noqa: E402

from campus247.application.policy_rules.service import PolicyRulesService  # noqa: E402
from campus247.domain.policy_rules.variables import load_vocabulary  # noqa: E402
from campus247.infrastructure.repositories.sqlite_policy_rules import PolicyRulesStore  # noqa: E402
from campus247.ports.campus_ops import OpsError  # noqa: E402
from campus247.ports.identity import IdentityRole  # noqa: E402
from campus247.presentation.campus_ops import register_ops_errors  # noqa: E402
from campus247.presentation.policy_rules import create_policy_rules_router, register_policy_rule_errors  # noqa: E402

UNITS = {}
for line in (ROOT / "data" / "rag_v2_index" / "units.jsonl").read_text(encoding="utf-8").splitlines():
    pass  # loaded lazily below to keep collection cheap

ADMIN = person(sid(2000), IdentityRole.KNOWLEDGE_ADMIN)
OTHER_ADMIN = person(sid(2001), IdentityRole.KNOWLEDGE_ADMIN)
CONTRIB = person(sid(2002), IdentityRole.KNOWLEDGE_CONTRIBUTOR)
STUDENT = person(sid(1), IdentityRole.STUDENT)


@pytest.fixture(scope="module")
def units():
    from campus247.infrastructure.knowledge.rag_v2_units import RagV2Units
    return RagV2Units(ROOT / "data" / "rag_v2_index")


@pytest.fixture()
def svc(tmp_path, units):
    clock = type("C", (), {"now": NOW, "__call__": lambda self: self.now})()
    s = PolicyRulesService(PolicyRulesStore(tmp_path / "rules.sqlite3"), load_vocabulary(ROOT / "config" / "policy" / "variables.toml"),
        units.text, units.release, clock=clock, signing_key="k")
    s.clock_obj = clock
    result = s.seed_from_directory(ROOT / "config" / "policy" / "rules", ROOT / "config" / "policy" / "gold")
    assert not result["failed"], result["failed"]
    return s


def attendance_body(svc):
    return copy.deepcopy(next(r["body"] for r in svc.records() if r["body"]["rule_id"] == "attendance-requirement"))


def test_seed_publishes_six_verified_rules_and_is_idempotent(svc):
    assert len(svc.records()) == 6 and {r["status"] for r in svc.records()} == {"PUBLISHED"}
    again = svc.seed_from_directory(ROOT / "config" / "policy" / "rules", ROOT / "config" / "policy" / "gold")
    assert again["published"] == [] and len(again["skipped"]) == 6
    assert {t["topic"] for t in svc.topics()} == {"ATTENDANCE_REQUIREMENT", "COURSE_PASS", "ACADEMIC_WARNING", "FORCED_WITHDRAWAL_WARNINGS",
        "GRADUATION_ELIGIBILITY", "HONORS_DEMOTION"}


def test_attendance_rule_answers_with_proof_and_threshold(svc):
    r = svc.evaluate("ATTENDANCE_REQUIREMENT", {"attendance.absent_periods": 7, "course.total_periods": 30})  # 23.3 %
    assert r["outcome"] == "NOT_SATISFIED"
    assert r["proof"]["children"][0]["children"][0]["source"]["path"].startswith("Điều 9")
    th = [t for t in r["thresholds"] if t["var"] == "attendance.absent_periods"]
    assert th and th[0]["flip_at"] == 6  # 6/30 = 20 % is not over 20 %, 7/30 is
    ok = svc.evaluate("ATTENDANCE_REQUIREMENT", {"attendance.absent_periods": 6, "course.total_periods": 30})
    assert ok["outcome"] == "SATISFIED"
    assert svc.evaluate("ATTENDANCE_REQUIREMENT", {})["outcome"] == "UNDETERMINED"


def test_warning_rule_cases(svc):
    base = {"semester.failed_credits": 4, "semester.registered_credits": 20, "study.debt_credits": 10, "semester.is_first": False,
        "gpa.semester": 2.0, "student.year_level": 2, "gpa.cumulative": 2.0}
    assert svc.evaluate("ACADEMIC_WARNING", base)["outcome"] == "NOT_SATISFIED"
    assert svc.evaluate("ACADEMIC_WARNING", {**base, "study.debt_credits": 25})["outcome"] == "SATISFIED"
    assert svc.evaluate("ACADEMIC_WARNING", {**base, "study.debt_credits": 24})["outcome"] == "NOT_SATISFIED"  # "vượt quá 24"
    assert svc.evaluate("ACADEMIC_WARNING", {**base, "semester.failed_credits": 10})["outcome"] == "NOT_SATISFIED"  # 50 % exactly
    assert svc.evaluate("ACADEMIC_WARNING", {**base, "semester.failed_credits": 11})["outcome"] == "SATISFIED"
    assert svc.evaluate("ACADEMIC_WARNING", {**base, "gpa.semester": 0.9, "semester.is_first": True})["outcome"] == "NOT_SATISFIED"
    assert svc.evaluate("ACADEMIC_WARNING", {**base, "gpa.semester": 0.7, "semester.is_first": True})["outcome"] == "SATISFIED"
    assert svc.evaluate("ACADEMIC_WARNING", {**base, "student.year_level": 4, "gpa.cumulative": 1.79})["outcome"] == "SATISFIED"
    assert svc.evaluate("ACADEMIC_WARNING", {**base, "student.year_level": 4, "gpa.cumulative": 1.8})["outcome"] == "NOT_SATISFIED"


def test_graduation_and_demotion_and_withdrawal(svc):
    grad = {"graduation.requirements_complete": True, "gpa.cumulative": 2.0, "criminal.liability": False, "discipline.level": "NONE"}
    assert svc.evaluate("GRADUATION_ELIGIBILITY", grad)["outcome"] == "SATISFIED"
    assert svc.evaluate("GRADUATION_ELIGIBILITY", {**grad, "gpa.cumulative": 1.99})["outcome"] == "NOT_SATISFIED"
    assert svc.evaluate("GRADUATION_ELIGIBILITY", {**grad, "discipline.level": "SUSPENSION"})["outcome"] == "NOT_SATISFIED"
    assert svc.evaluate("HONORS_DEMOTION", {"gpa.cumulative": 3.5, "retake.credits": 9, "program.total_credits": 150, "discipline.level": "NONE"})["outcome"] == "SATISFIED"
    assert svc.evaluate("HONORS_DEMOTION", {"gpa.cumulative": 3.5, "retake.credits": 7, "program.total_credits": 150, "discipline.level": "NONE"})["outcome"] == "NOT_SATISFIED"
    assert svc.evaluate("FORCED_WITHDRAWAL_WARNINGS", {"warnings.consecutive": 3, "warnings.total": 3, "program.kind": "BACHELOR"})["outcome"] == "SATISFIED"
    assert svc.evaluate("FORCED_WITHDRAWAL_WARNINGS", {"warnings.consecutive": 2, "warnings.total": 4, "program.kind": "BACHELOR"})["outcome"] == "NOT_SATISFIED"
    assert svc.evaluate("FORCED_WITHDRAWAL_WARNINGS", {"warnings.consecutive": 2, "warnings.total": 5, "program.kind": "ENGINEER_SPECIAL"})["outcome"] == "NOT_SATISFIED"
    unknown_kind = svc.evaluate("FORCED_WITHDRAWAL_WARNINGS", {"warnings.consecutive": 2, "warnings.total": 5})
    assert unknown_kind["outcome"] == "UNDETERMINED" and unknown_kind["missing"] == ["program.kind"]


def test_gold_cases_from_regulation_text(svc):
    """Gold files are scenarios authored from the regulation wording; each carries a span the code re-verifies."""
    import json
    for path in sorted((ROOT / "config" / "policy" / "gold").glob("*.json")):
        gold = json.loads(path.read_text(encoding="utf-8"))
        rule = json.loads((ROOT / "config" / "policy" / "rules" / path.name).read_text(encoding="utf-8"))
        assert len(gold["cases"]) >= 40, path.name
        for case in gold["cases"]:
            span = case["source_span"]
            assert span["quote"] in svc.text_of_unit(span["unit_id"]), (path.name, span)
        vectors = svc.store.vectors(rule["rule_id"], 1)
        report = svc.gold_report(vectors)
        assert report["total"] == len(gold["cases"]) and report["rate"] >= 0.98 and report["mismatch_pending"] == 0, (path.name, report)


def test_authoring_workflow_publish_with_preview_confirm(svc):
    body = attendance_body(svc)
    body["description"] = "bản sửa"
    with pytest.raises(OpsError) as e:
        svc.create_draft(STUDENT, body)
    assert e.value.status == 403
    draft = svc.create_draft(CONTRIB, body)
    report = svc.validate_draft(CONTRIB, draft["id"])
    assert report["issues"] == [] and report["mismatches"] == [] and report["vector_count"] > 10
    with pytest.raises(OpsError) as e:  # not yet reviewed
        svc.publish_preview(ADMIN, draft["id"])
    assert e.value.code == "RULE_NOT_APPROVED"
    with pytest.raises(OpsError) as e:  # contributor cannot review
        svc.review(CONTRIB, draft["id"], "approved", "đã đối chiếu nguồn")
    assert e.value.status == 403
    svc.review(ADMIN, draft["id"], "approved", "đã đối chiếu nguồn")
    pv = svc.publish_preview(ADMIN, draft["id"])
    with pytest.raises(OpsError) as e:  # token bound to the actor
        svc.confirm(OTHER_ADMIN, pv["preview_id"], pv["confirmation_token"], "k1")
    assert e.value.code in {"PREVIEW_EXPIRED", "CONFIRMATION_REQUIRED"}
    with pytest.raises(OpsError) as e:
        svc.confirm(ADMIN, pv["preview_id"], "bad", "k1")
    assert e.value.code == "CONFIRMATION_REQUIRED"
    done = svc.confirm(ADMIN, pv["preview_id"], pv["confirmation_token"], "k1")
    assert done["version"] == 2 and done["status"] == "PUBLISHED"
    again = svc.confirm(ADMIN, pv["preview_id"], pv["confirmation_token"], "k1")  # idempotent replay
    assert again["version"] == 2 and again["replayed"] is True
    versions = svc.store.versions("attendance-requirement")
    assert [v["status"] for v in versions] == ["RETIRED", "PUBLISHED"]
    # old version stays readable to reproduce an earlier decision
    assert svc.store.get_version("attendance-requirement", 1)["body"]["rule_id"] == "attendance-requirement"
    assert next(r for r in svc.records() if r["body"]["rule_id"] == "attendance-requirement")["version"] == 2


def test_publish_blocked_by_bad_quote_and_wrong_value(svc):
    body = attendance_body(svc)
    body["when"]["all"][0]["not"]["pred"]["value"] = 30
    d = svc.create_draft(ADMIN, body)
    codes = {i["code"] for i in svc.validate_draft(ADMIN, d["id"])["issues"]}
    assert "VALUE_NOT_IN_QUOTE" in codes
    body2 = attendance_body(svc)
    body2["when"]["all"][0]["not"]["source"]["quote"] = "câu này không có trong quy chế"
    d2 = svc.create_draft(ADMIN, body2)
    assert "QUOTE_NOT_VERBATIM" in {i["code"] for i in svc.validate_draft(ADMIN, d2["id"])["issues"]}
    svc.review(OTHER_ADMIN, d2["id"], "approved", "ghi chú đủ dài")
    with pytest.raises(OpsError) as e:
        svc.publish_preview(ADMIN, d2["id"])
    assert e.value.code == "RULE_VALIDATION_FAILED"


def test_rule_goes_stale_when_a_cited_unit_changes(svc, units):
    assert svc.check_staleness() == []
    changed = lambda uid: (units.text(uid) + " (sửa đổi)") if uid == "9cfbe01c0aca8f15" else units.text(uid)  # noqa: E731
    svc.text_of_unit = changed
    stale = svc.check_staleness()
    assert [s["rule_id"] for s in stale] == ["attendance-requirement"]
    r = svc.evaluate("ATTENDANCE_REQUIREMENT", {"attendance.absent_periods": 1, "course.total_periods": 30})
    assert r["outcome"] == "UNDETERMINED" and r["reason"] == "RULE_STALE"
    assert svc.summary() == {"active": 5, "stale": 1}


def client(svc, who):
    app = FastAPI()
    register_ops_errors(app)
    register_policy_rule_errors(app)
    app.include_router(create_policy_rules_router(svc))

    @app.middleware("http")
    async def ident(request, call_next):
        request.state.identity = who
        return await call_next(request)
    return TestClient(app)


def test_http_public_flow_and_errors(svc):
    c = client(svc, STUDENT)
    assert len(c.get("/v1/policy-simulator/topics").json()["topics"]) == 6
    form = c.get("/v1/policy-simulator/topics/ATTENDANCE_REQUIREMENT/form").json()
    assert [f["var"] for f in form["fields"]] == ["attendance.absent_periods", "course.total_periods"]
    assert c.get("/v1/policy-simulator/topics/NOPE/form").status_code == 404
    ok = c.post("/v1/policy-simulator/evaluate", json={"topic": "ATTENDANCE_REQUIREMENT", "inputs": {"attendance.absent_periods": 3, "course.total_periods": 30}})
    assert ok.status_code == 200 and ok.json()["outcome"] == "SATISFIED" and ok.json()["disclaimer_code"] == "SIMULATION_NOT_DECISION"
    bad = c.post("/v1/policy-simulator/evaluate", json={"topic": "ATTENDANCE_REQUIREMENT", "inputs": {"attendance.absent_periods": -1, "x": 1}})
    assert bad.status_code == 422 and bad.json()["code"] == "POLICY_INPUT_INVALID"
    assert {(e["var"], e["code"]) for e in bad.json()["errors"]} == {("attendance.absent_periods", "OUT_OF_RANGE"), ("x", "UNKNOWN_VARIABLE")}
    wi = c.post("/v1/policy-simulator/what-if", json={"topic": "ATTENDANCE_REQUIREMENT", "inputs": {"attendance.absent_periods": 3, "course.total_periods": 30}, "vary": "attendance.absent_periods"})
    assert wi.status_code == 200 and wi.json()["samples"][0]["outcome"] == "SATISFIED" and wi.json()["samples"][-1]["outcome"] == "NOT_SATISFIED"
    # students cannot open the authoring API
    assert c.get("/v1/policy-rules").status_code == 403
    # inputs are never stored, only counters
    assert svc.store.stats("2000-01-01") and "inputs" not in str(svc.store.stats("2000-01-01"))


def test_http_rate_limit(svc):
    app = FastAPI()
    register_ops_errors(app)
    register_policy_rule_errors(app)
    ticks = iter(range(1000))
    app.include_router(create_policy_rules_router(svc, now=lambda: next(ticks) * 0.01))

    @app.middleware("http")
    async def ident(request, call_next):
        request.state.identity = STUDENT
        return await call_next(request)
    c = TestClient(app)
    codes = [c.post("/v1/policy-simulator/evaluate", json={"topic": "COURSE_PASS", "inputs": {"grade.course_score": 5}}).status_code for _ in range(32)]
    assert codes[:30] == [200] * 30 and codes[30] == 429


def test_performance_p95_under_50ms(svc):
    import time
    times = []
    for _ in range(100):
        t = time.perf_counter()
        svc.evaluate("ACADEMIC_WARNING", {"semester.failed_credits": 4, "semester.registered_credits": 20, "study.debt_credits": 10,
            "semester.is_first": False, "gpa.semester": 2.0, "student.year_level": 2, "gpa.cumulative": 2.0})
        times.append((time.perf_counter() - t) * 1000)
    times.sort()
    assert times[94] < 50, times[-5:]


def test_match_finds_topic_and_only_verbatim_values(svc):
    hit = svc.match("Em nghỉ 25 tiết trong môn có 45 tiết thì có sao không?")
    assert hit["topic"] == "ATTENDANCE_REQUIREMENT"
    # two period fields share one unit word, so no value is guessed
    assert hit["values"] == {} and hit["evidence"] == []
    none = svc.match("Thư viện mở cửa lúc mấy giờ?")
    assert none["topic"] is None and none["values"] == {}
    with pytest.raises(OpsError):
        svc.match("   ")


def test_match_values_are_literally_in_the_sentence(svc):
    for q in ["Em có 120 tín chỉ tích lũy, điểm trung bình 2,6 thì có đủ điều kiện tốt nghiệp không?",
              "điểm quá trình 6 điểm, thi 4 điểm thì có đạt học phần không"]:
        hit = svc.match(q)
        for ev in hit["evidence"]:
            assert ev["snippet"] in q
            assert hit["values"][ev["var"]] is not None


def test_match_endpoint_works_for_students(svc):
    r = client(svc, STUDENT).post("/v1/policy-simulator/match", json={"text": "Em nghỉ học 25 tiết có sao không"})
    assert r.status_code == 200 and "matches" in r.json()
    assert client(svc, STUDENT).post("/v1/policy-simulator/match", json={"text": ""}).status_code == 422
