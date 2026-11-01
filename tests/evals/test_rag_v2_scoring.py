"""I5: synthetic mutations and offline campaign/probe contracts; no live data."""
import asyncio
import json
import socket
from argparse import Namespace
from copy import deepcopy

import pytest
import httpx

from evals.runners import rag_v2_eval as runner
from evals.runners import rag_v2_gate_compare as comparison
from evals.runners import rag_v2_newdoc as newdoc
from evals.runners import rag_v2_suite as suite


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("I5 must make zero network calls")
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", denied)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", denied)


def case(cid="c", **changes):
    return {"case_id": cid, "group_id": "g", "family": "khac", "variant": "form",
            "split": "holdout", "expected": "answer", "required_facts": ["Mượn 07 ngày"],
            "forbidden_facts": ["Mọi người được miễn học phí"],
            "gold": [{"chunk_id": "gold", "quote": "Dịch vụ cho phép mượn 07 ngày."}], **changes}


def row(cid="c", repeat=1, **changes):
    return {"case_id": cid, "repeat": repeat, "outcome_class": "answer",
            "answer_text": "Mượn 07 ngày", "citation_chunk_ids": ["gold"], "citation_count": 1,
            "final_event": True, "seconds": 1, "first_byte_seconds": .1, "http_status": 200,
            **changes}


MUTATIONS = []
for days in (3, 5, 7, 9, 12, 14):
    MUTATIONS.extend([
        (f"được gia hạn {days:02d} ngày", f"không được gia hạn {days:02d} ngày", [], False),
        (f"Nhóm Alpha được mượn {days} ngày", f"Nhóm Beta được mượn {days} ngày", [], False),
        (f"Mượn {days} ngày", f"Bảo hành {days} ngày; mượn {days + 10} ngày", [], False),
        (f"Giới hạn {days} kg", f"Giới hạn {days} tấn", [], False),
        (f"Mượn {days} ngày", f"Mượn {days} ngày. Mọi người được miễn học phí.",
         ["Mọi người được miễn học phí"], False),
        (f"Phí {days * 1000} đồng", f"Phí {days} nghìn đồng", [], True),
        (f"Mượn {days:02d} ngày", f"Thời gian mượn: {days} ngày", [], True),
        (f"Mượn {days} ngày", f"MƯỢN {days} NGÀY", [], True),
    ])
MUTATIONS.extend([
    ("không thu phí mượn", "Dịch vụ mượn hoàn toàn miễn phí", [], True),
    ("Mượn ba ngày", "Mượn 3 ngày", [], True),
    ("Gia hạn 3 ngày nếu có giấy xác nhận", "Gia hạn 3 ngày", [], False),
    ("không được gia hạn 3 ngày", "được gia hạn 3 ngày", [], False),
    ("Mượn 7 ngày", "Không được mượn 7 ngày. Mượn 7 ngày.", [], False),
    ("Thu phí 2.5 đồng", "Thu phí 25 đồng", [], False),
])


@pytest.mark.parametrize("gold,answer,forbidden,expected", MUTATIONS)
def test_mutation(gold, answer, forbidden, expected):
    actual = runner.fact_matches(gold, answer) and not any(
        runner.fact_matches(f, answer) for f in forbidden)
    assert actual is expected


def test_shared_scoring_rejects_forbidden_in_comparison():
    answer = row(answer_text="Mượn 07 ngày. Mọi người được miễn học phí.")
    counts, _, _, _ = comparison.summarize({"c": case()}, [answer])
    assert counts["full"] == 0 and counts["thin"] == 1


def scoring():
    from evals.runners import rag_v2_scoring
    return rag_v2_scoring


def test_a2_is_statement_measurement_not_citation_count():
    m = runner.score_records([row()], [case()])["metrics"]
    assert m["A2"]["passed"] is None
    assert m["uncited_answer"]["value"] == 0
    m = runner.score_records([row(answer_text="Mượn 7 ngày; phí 999 đồng",
        cited_texts=["Cho phép mượn 07 ngày."])], [case()])["metrics"]
    assert m["A2"]["value"] == 1 and m["A2"]["passed"] is False


def test_unsupported_numbers_dates_codes_money_and_equivalents():
    s = scoring()
    assert s.unsupported_statements("Phí 1 nghìn đồng. Mượn 7 ngày.",
                                    ["Phí 1000 đồng, mượn 07 ngày."]) == []
    for text in ("Hạn 14/11/2026", "Mã QX-901", "Phí 999 đồng", "Mượn 8 ngày"):
        assert s.unsupported_statements(text, ["Hạn 13/11/2026; QX-900; phí 1000 đồng; mượn 7 ngày"])
    assert s.unsupported_statements("Nguồn không có số", []) == []  # Explicit deterministic limit.


def test_three_repeats_require_distinct_indices_even_across_sources():
    records = [row(source_run=str(i)) for i in range(3)]
    report = runner.score_records(records, [case()])
    assert not report["coverage"]["holdout_three_repeats_complete"]
    assert report["metrics"]["A6"]["passed"] is None
    with pytest.raises(ValueError):
        runner.score_records(records, [case()], strict=True)


@pytest.mark.parametrize("field", ["cases_sha256", "engine", "campaign_id"])
def test_strict_campaign_rejects_mixed_manifest(field):
    base = {"cases_sha256": runner.fingerprint([case()]), "engine": "v2", "campaign_id": "one"}
    manifests = [base, dict(base, **{field: "different"})]
    with pytest.raises(ValueError):
        runner.score_records([row(repeat=i) for i in (1, 2, 3)], [case()],
                             strict=True, manifests=manifests)


def test_missing_repeats_and_mixed_case_set_comparison():
    with pytest.raises(ValueError):
        runner.score_records([row()], [case()], strict=True)
    a = runner.score_records([row()], [case()])
    b = runner.score_records([row("other")], [case("other")])
    with pytest.raises(ValueError):
        runner.compare_reports(a, b, strict=True)


def test_first_attempt_and_after_retry_are_separate():
    journal = [row(attempt_index=1, outcome_class="error", error="Timeout"), row(attempt_index=2)]
    report = scoring().attempt_metrics([row(attempt_index=2)], journal)
    assert report["first_attempt"]["value"] == 1
    assert report["after_retry"]["value"] == 0
    assert report["all_attempts"]["value"] == .5


def test_distribution_requires_twenty_percent_and_four_variants():
    s = scoring()
    variants = ("form", "no_diacritics", "keyword", "slang")
    positive = [case(str(i), variant=v) for i, v in enumerate(variants)]
    assert "negative_share" in s.distribution_issues(positive)
    negatives = [case("n" + str(i), group_id="n", variant=v, expected="abstain")
                 for i, v in enumerate(variants)]
    assert s.distribution_issues(positive + negatives) == []
    assert s.distribution_issues(positive + negatives[:-1])


def test_wilson_and_cluster_bootstrap_known_data():
    s = scoring()
    ci = s.bootstrap_ci_by_group([1] * 16 + [0] * 344, [str(i // 12) for i in range(360)], samples=2000)
    assert ci["wilson"][0] == pytest.approx(.0275, abs=.0001)
    assert ci["wilson"][1] == pytest.approx(.0710, abs=.0001)
    assert ci == s.bootstrap_ci_by_group([1] * 16 + [0] * 344,
        [str(i // 12) for i in range(360)], samples=2000)
    assert s.bootstrap_ci_by_group([1, 1, 1], ["doc"] * 3)["bootstrap"] == [1, 1]
    assert s.bootstrap_ci_by_group([], [])["bootstrap"] is None


def test_newdoc_errors_and_short_quotes(monkeypatch, capsys):
    cases = [case(), case("n", expected="abstain")]
    cases[0]["quote"] = cases[0]["gold"][0]["quote"]
    records = [{"case_id": "c", "kind": "answer", "text": "Mượn 07 ngày", "cited_quotes": ["", "M"]},
               {"case_id": "n", "kind": "transient_error", "text": "", "cited_quotes": []}]
    payloads = {"cases": "\n".join(json.dumps(c) for c in cases), "results": json.dumps({"records": records})}
    monkeypatch.setattr(newdoc.Path, "read_text", lambda p, **kw: payloads[str(p)])
    assert newdoc.score(Namespace(cases="cases", results="results")) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["errors"] == 1 and report["correctly_declined"] == 0
    assert report["cited_quote_overlaps_gold"] == 0


@pytest.mark.parametrize("records", [[], [row(), row()]])
def test_newdoc_missing_duplicate_rejected(records):
    with pytest.raises(ValueError):
        scoring().validate_records(records, [case()], repeats=1)


def test_missing_route_is_not_measured_or_in_routing_denominator():
    c = {"case_id": "r", "suite": "routing", "turns": [{"content": "q"}],
         "notes": {"expected_route": "grounded_faq"}, "expect": {"outcome_any": ["answer"],
         "must_contain_any": [], "must_contain_all": [], "must_not_contain": [], "no_contact_values": False}}
    r = {"case_id": "r", "turns": [{"final": {"outcome_kind": "answer", "content": "Đã tra cứu"}}]}
    a = suite.assess(c, r)
    assert a["route_unmeasured"] is True
    result = suite.summarize([r], [c])["suites"]["routing"]
    assert result["unmeasured"] == 1 and result["evaluated"] == 0
    assert result["passed"] == 0 and result["pass_rate"] is None


def test_cached_authorized_probe_context_equals_runtime(monkeypatch):
    from evals.runners import rag_v2_context_probe as probe
    from campus247.rag_v2.adapters.memory_index import MemoryIndex
    from campus247.rag_v2.types import Unit
    units = [Unit(unit_id=uid, chunk_ids=(uid,), document_id=uid, version_id="v",
                  doc_title="Nguồn", doc_family="khac", kind="page", path="", page=1,
                  text="Thư viện cho mượn sách 7 ngày") for uid in ("yes", "no")]
    cached = probe.cached_embed([{"text": "mượn sách thư viện", "embedding": [1., 0.]}])
    index = MemoryIndex.from_units(units, [[1., 0.], [1., 0.]], cached)
    chunks = {u.unit_id: {"chunk_id": u.unit_id, "text": u.text, "doc_title": u.doc_title,
              "document_id": u.document_id, "version_id": u.version_id, "page": 1, "section_label": ""}
              for u in units}
    authorized = probe.authorized_index(index, chunks, allowed={"yes"})
    assert set(authorized.all_ids()) == {"yes"}
    context = asyncio.run(probe.runtime_context(authorized, "mượn sách thư viện"))
    assert context["chunk_ids"] == ["yes"]
    assert context["context_sha256"] == probe.context_hash(context["units"])
    with pytest.raises(ValueError):
        asyncio.run(cached("missing cache entry"))


@pytest.mark.parametrize("answer", ["Mượn 14 ngày và bảo hành 7 ngày", "Mượn | 14 ngày | Bảo hành | 7 ngày"])
def test_number_keeps_nearest_label_in_one_sentence_or_table(answer):
    assert not runner.fact_matches("Mượn 7 ngày", answer)


def test_journal_without_first_attempt_does_not_invent_first_attempt_rate():
    report = scoring().attempt_metrics([row(attempt_index=2)], [row(attempt_index=2)])
    assert report["first_attempt"]["value"] is None


def test_score_and_gate_cli_exit_codes_and_strict(monkeypatch, capsys):
    cases = [case(str(i), variant=v, group_id="pos") for i, v in enumerate(scoring().VARIANTS)]
    cases += [case("n" + str(i), variant=v, group_id="neg", expected="abstain")
              for i, v in enumerate(scoring().VARIANTS)]
    records = [row(c["case_id"], repeat=i, attempt_index=1,
                   outcome_class="answer" if c["expected"] == "answer" else "refuse",
                   cited_texts=["Mượn 07 ngày"]) for c in cases for i in (1, 2, 3)]
    data = {"records": records, "metadata": {"cases_sha256": runner.fingerprint(cases),
            "engine": "v2", "campaign_id": "synthetic"}}
    monkeypatch.setattr(runner.Path, "read_text", lambda *a, **kw: json.dumps(data))
    monkeypatch.setattr(runner, "read_jsonl", lambda p: cases)
    monkeypatch.setattr(runner, "write_json", lambda *a, **kw: None)
    monkeypatch.setattr(runner, "corpus_texts", lambda: {})
    args = ["--results", "synthetic.json", "--cases", "synthetic.jsonl", "--strict"]
    assert runner.main(["gate", *args]) == 0
    records[0]["answer_text"] += ". Mọi người được miễn học phí."
    assert runner.main(["score", *args]) == 0
    assert runner.main(["gate", *args]) == 1
    data["records"] = records[:-1]
    with pytest.raises(SystemExit) as e:
        runner.main(["score", *args])
    assert e.value.code == 2
    assert "CI" not in capsys.readouterr().err


def test_manifest_scoring_uses_selected_split_not_other_split():
    cases = [case(), case("dev", split="dev")]
    manifest = {"cases_sha256": runner.fingerprint(cases[:1]), "engine": "v2", "campaign_id": "x"}
    report = runner.score_records([row(repeat=i) for i in (1, 2, 3)], cases,
                                 strict=True, manifests=[manifest])
    assert report["provenance"]["issues"] == []


def test_inline_citation_markers_are_not_unsupported_values():
    assert scoring().unsupported_statements("Mượn 7 ngày [S1] [2] [CIT-007].", ["Mượn 7 ngày"]) == []


def test_a2_date_equivalence_does_not_split_date_into_decimal_values():
    assert scoring().unsupported_statements("Hạn 2026-11-13.", ["Hạn ngày 13 tháng 11 năm 2026"]) == []
    assert scoring().unsupported_statements("Hạn 13/11/2026.", ["Hạn 13.11.2026"]) == []


def test_strict_comparison_rejects_two_different_campaigns():
    manifest = {"cases_sha256": runner.fingerprint([case()]), "engine": "v2", "campaign_id": "one"}
    rows = [row(repeat=i) for i in (1, 2, 3)]
    a = runner.score_records(rows, [case()], manifests=[manifest], strict=True)
    b = runner.score_records(rows, [case()], manifests=[dict(manifest, campaign_id="two")], strict=True)
    with pytest.raises(ValueError):
        runner.compare_reports(a, b, strict=True)


def test_a_fact_listed_from_a_negated_gold_statement_may_be_stated_inside_a_negated_clause():
    from evals.runners import rag_v2_scoring as scoring
    gold = [{"chunk_id": "c", "quote": "Tổng: 181TC (Không tính HP giáo dục thể chất, Giáo dục quốc phòng và An ninh;)"}]
    case = {"required_facts": ["181TC", "giáo dục thể chất"], "forbidden_facts": [], "gold": gold}
    answer = "Tổng số tín chỉ là 181TC. Tổng 181TC không tính học phần giáo dục thể chất."
    assert scoring.fact_errors(case, answer) == {"missing_facts": [], "forbidden_facts": []}


def test_polarity_still_catches_a_contradiction_of_a_positive_gold_statement():
    from evals.runners import rag_v2_scoring as scoring
    case = {"required_facts": ["miễn học phí"], "forbidden_facts": [],
            "gold": [{"chunk_id": "c", "quote": "Sinh viên diện này được miễn học phí."}]}
    assert scoring.fact_errors(case, "Sinh viên diện này được miễn học phí.")["missing_facts"] == []
    assert scoring.fact_errors(case, "Sinh viên diện này không được miễn học phí.")["missing_facts"] == ["miễn học phí"]


def test_a_full_stop_inside_a_token_does_not_split_a_clause():
    from evals.runners import rag_v2_scoring as scoring
    assert scoring.fact_matches("https://office.com", "Truy cập trang https://office.com, ấn Sign in.")


def test_a_gold_sentence_wrapped_across_pdf_lines_keeps_its_polarity():
    from evals.runners import rag_v2_scoring as scoring
    case = {"required_facts": ["cảnh báo học tập"], "forbidden_facts": [], "gold": [{"chunk_id": "c", "quote":
            "5. Sinh viên không đăng ký học tập, nếu không có lý do chính đáng sẽ bị\ncảnh báo học tập."}]}
    answer = "Sinh viên không đăng ký học tập, nếu không có lý do chính đáng sẽ bị cảnh báo học tập."
    assert scoring.fact_errors(case, answer)["missing_facts"] == []
    case["gold"] = [{"chunk_id": "c", "quote": "được Hiệu trưởng đồng ý với số tín chỉ tích lũy tại trường khác\n"
                                                "(nếu có) không vượt quá 25%."}]
    case["required_facts"] = ["Hiệu trưởng đồng ý"]
    assert scoring.fact_errors(case, "Nếu được Hiệu trưởng đồng ý với số tín chỉ (nếu có) không vượt quá 25%.")[
        "missing_facts"] == []
    # A separate upper-case line is still its own clause: its negation does not widen a positive fact.
    case["gold"] = [{"chunk_id": "c", "quote": "Sinh viên được miễn học phí.\nKhông áp dụng cho học phần học lại."}]
    case["required_facts"] = ["miễn học phí"]
    assert scoring.fact_errors(case, "Sinh viên không được miễn học phí.")["missing_facts"] == ["miễn học phí"]


def test_a_unit_token_with_digits_is_bound_whole():
    from evals.runners import rag_v2_scoring as scoring
    assert scoring.fact_matches("5.000 m²", "Tòa nhà Thư viện có tổng diện tích khoảng 5.000 m².")
    assert scoring.fact_matches("#002A5C", "Màu xanh nhận diện có mã HEX #002A5C.")
    assert not scoring.fact_matches("5.000 m²", "Tòa nhà Thư viện có tổng diện tích khoảng 5.000 ha.")
