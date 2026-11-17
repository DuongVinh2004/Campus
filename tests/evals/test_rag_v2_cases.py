"""Small in-memory fixtures: no real shards, corpus, temporary files or services."""
import hashlib
import importlib.util
import json
from copy import deepcopy
from io import BytesIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("rag_v2_cases", ROOT / "evals/runners/rag_v2_cases.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def fixture():
    chunks = [{"chunk_id": "c1", "doc_family": "quy_che",
               "content_text": "Sinh viên đăng ký ít nhất 12 tín chỉ mỗi kỳ. Hạn đăng ký là ngày 15/09. Mức sai: 99 tín chỉ."},
              {"chunk_id": "c2", "doc_family": "quy_che",
               "content_text": "ĐƯỢC HOÃN HỌC khi có giấy xác nhận.\nKhông được thiếu giấy tờ."}]
    questions = ("Mỗi kỳ phải đăng ký ít nhất bao nhiêu tín chỉ?", "Moi ky dang ky bao nhieu tin chi?",
                 "đăng ký tín chỉ", "sv đk tối thiểu mấy tc/kỳ ạ?")
    cases = [{"case_id": f"R2-X-{i:04}", "group_id": "G-X-001", "split": "", "family": "quy_che",
              "variant": variant, "question": question, "expected": "answer",
              "gold": [{"chunk_id": "c1", "quote": "Sinh viên đăng ký ít nhất 12 tín chỉ mỗi kỳ."}],
              "required_facts": ["12 tín chỉ"], "forbidden_facts": ["99 tín chỉ"]}
             for i, (variant, question) in enumerate(zip(runner.VARIANTS, questions), 1)]
    return cases, chunks


def negative():
    return {"case_id": "R2-N-0001", "group_id": "G-N-001", "split": "", "family": "gan_mien_vang",
            "variant": "form", "question": "Trường có học bổng Sao Hỏa không?", "expected": "abstain",
            "gold": [], "required_facts": [], "forbidden_facts": [],
            "absent_terms": ["học bổng Sao Hỏa", "trợ cấp hành tinh đỏ", "quỹ khuyến học liên hành tinh"]}


def codes(cases, chunks):
    return {error["code"] for error in runner.validate_cases(cases, chunks)}


def test_valid_four_variants_and_singleton_negatives():
    cases, chunks = fixture()
    abstain = negative()
    clarify = dict(abstain, case_id="R2-N-0002", group_id="G-N-002", family="mo_ho", expected="clarify")
    clarify.pop("absent_terms")
    assert runner.validate_cases([*cases, abstain, clarify], chunks) == []


@pytest.mark.parametrize("field", sorted(runner.FIELDS))
def test_every_schema_field_is_required(field):
    cases, chunks = fixture()
    cases[0].pop(field)
    errors = runner.validate_cases(cases, chunks)
    assert any(error["code"] == "MISSING_FIELDS" and field in error["message"] for error in errors)


@pytest.mark.parametrize("field,value", [("case_id", []), ("group_id", {}), ("question", 4),
    ("split", []), ("family", "unknown"), ("variant", {}), ("expected", "refuse"),
    ("gold", {}), ("gold", [None]), ("gold", [{"chunk_id": [], "quote": "x"}]),
    ("required_facts", "12"), ("required_facts", [None]), ("forbidden_facts", [""]),
    ("question", "   ")])
def test_malformed_values_report_errors_without_crashing(field, value):
    cases, chunks = fixture()
    cases[0][field] = value
    assert runner.validate_cases(cases, chunks)


def test_non_object_and_empty_inputs():
    assert "CASE_SCHEMA" in codes([None], [])
    assert codes([], []) == {"EMPTY_DATASET", "EMPTY_CORPUS"}


def test_duplicate_case_and_group_variant_report_case_id():
    cases, chunks = fixture()
    errors = runner.validate_cases([*cases, deepcopy(cases[0])], chunks)
    assert {"DUPLICATE_CASE_ID", "DUPLICATE_GROUP_VARIANT", "ANSWER_GROUP_VARIANTS"} <= {e["code"] for e in errors}
    assert any(e["case_id"] == cases[0]["case_id"] and e["code"] == "DUPLICATE_CASE_ID" for e in errors)


def test_group_id_cannot_be_reused_for_negative_cases():
    cases, chunks = fixture()
    first = negative()
    second = dict(first, case_id="R2-N-0002", variant="slang")
    assert "DUPLICATE_GROUP_ID" in codes([*cases, first, second], chunks)


@pytest.mark.parametrize("change", ["missing", "duplicate", "mixed_expected", "mixed_family", "mixed_split"])
def test_answer_groups_have_exactly_four_consistent_variants(change):
    cases, chunks = fixture()
    if change == "missing":
        cases.pop()
    elif change == "duplicate":
        cases[1]["variant"] = "form"
    else:
        field = change.removeprefix("mixed_")
        cases[1][field] = {"expected": "abstain", "family": "so_tay", "split": "dev"}[field]
    assert ("ANSWER_GROUP_VARIANTS" if change in {"missing", "duplicate"} else "INCONSISTENT_GROUP") in codes(cases, chunks)


@pytest.mark.parametrize("change,expected", [("unknown", "UNKNOWN_CHUNK"), ("case", "QUOTE_NOT_VERBATIM"),
    ("space", "QUOTE_NOT_VERBATIM"), ("short", "QUOTE_LENGTH"), ("long", "QUOTE_LENGTH"),
    ("no_gold", "ANSWER_WITHOUT_GOLD"), ("wrong_fact", "REQUIRED_FACT_NOT_GOLD"),
    ("empty_facts", "REQUIRED_FACT_COUNT"), ("too_many_facts", "REQUIRED_FACT_COUNT"),
    ("overlap", "FORBIDDEN_REQUIRED_OVERLAP"), ("unknown_forbidden", "FORBIDDEN_FACT_NOT_CORPUS"),
    ("family", "GOLD_FAMILY_MISMATCH")])
def test_gold_and_fact_integrity(change, expected):
    cases, chunks = fixture()
    case = cases[0]
    if change == "unknown":
        case["gold"][0]["chunk_id"] = "missing"
    elif change in {"case", "space", "short", "long"}:
        quote = case["gold"][0]["quote"]
        case["gold"][0]["quote"] = {"case": quote.upper(), "space": quote.replace(" ", "  "),
                                    "short": "12", "long": "x" * 301}[change]
    elif change == "no_gold":
        case["gold"] = []
    elif change == "wrong_fact":
        case["required_facts"] = ["ĐƯỢC HOÃN HỌC"]  # In corpus, but outside gold chunks.
    elif change == "empty_facts":
        case["required_facts"] = []
    elif change == "too_many_facts":
        case["required_facts"] *= 5
    elif change == "overlap":
        case["forbidden_facts"] = ["12"]
    elif change == "unknown_forbidden":
        case["forbidden_facts"] = ["9876543"]
    else:
        chunks[0]["doc_family"] = "ctdt"
    assert expected in codes(cases, chunks)


def test_facts_outside_quote_in_gold_content_and_multichunk_gold_are_valid():
    cases, chunks = fixture()
    for case in cases:
        case["gold"].append({"chunk_id": "c2", "quote": "ĐƯỢC HOÃN HỌC khi có giấy xác nhận."})
        case["required_facts"] = ["15/09", "Không được thiếu giấy tờ"]
    assert runner.validate_cases(cases, chunks) == []


@pytest.mark.parametrize("question", ["Dang ký sao?", "hoc phi …", "hoc phi\u200b", "hoc phi 😀"])
def test_no_diacritics_is_strict_ascii(question):
    cases, chunks = fixture()
    cases[1]["question"] = question
    assert "NON_ASCII_QUESTION" in codes(cases, chunks)


@pytest.mark.parametrize("question", ["học", "một hai ba bốn năm sáu bảy"])
def test_keyword_word_count(question):
    cases, chunks = fixture()
    cases[2]["question"] = question
    assert "KEYWORD_LENGTH" in codes(cases, chunks)


@pytest.mark.parametrize("term", ["ĐƯỢC HOÃN HỌC", "được hoãn học", "DUOC HOAN HOC", "duoc hoan hoc",
                                   "Được hoãn học", "được   hoãn\n học"])
def test_absent_terms_search_every_chunk_case_and_diacritic_insensitively(term):
    cases, chunks = fixture()
    case = negative()
    case["absent_terms"][1] = term
    errors = runner.validate_cases([*cases, case], chunks)
    assert any(error["case_id"] == case["case_id"] and error["code"] == "ABSENT_TERM_PRESENT" for error in errors)


@pytest.mark.parametrize("terms", [None, [], ["x", "y", 3], ["", "x", "y"]])
def test_absent_terms_are_required_for_near_domain_abstention(terms):
    cases, chunks = fixture()
    case = dict(negative(), absent_terms=terms)
    assert "ABSENT_TERMS_SCHEMA" in codes([*cases, case], chunks)


def test_absent_terms_must_be_present_but_have_no_fixed_count():
    cases, chunks = fixture()
    case = negative()
    case.pop("absent_terms")
    assert "ABSENT_TERMS_SCHEMA" in codes([*cases, case], chunks)
    case["absent_terms"] = ["quỹ khuyến học liên hành tinh"]
    assert runner.validate_cases([*cases, case], chunks) == []


def test_corpus_export_text_alias_and_conflicts():
    cases, chunks = fixture()
    for chunk in chunks:
        chunk["text"] = chunk.pop("content_text")
    assert runner.validate_cases(cases, chunks) == []
    chunks[0]["content_text"] = "conflicting text"
    assert "CORPUS_TEXT_CONFLICT" in codes(cases, chunks)
    assert "DUPLICATE_CHUNK_ID" in codes(cases, [chunks[1], chunks[1]])
    assert "CORPUS_SCHEMA" in codes(cases, [None, {"chunk_id": "empty", "text": None}])


def test_merge_is_deterministic_group_isolated_and_hashes_exact_utf8_bytes():
    cases, chunks = fixture()
    cases.append(negative())
    original = deepcopy(cases)
    payload, manifest = runner.merge_cases(cases, chunks)
    assert runner.merge_cases(list(reversed(cases)), chunks) == (payload, manifest)
    assert cases == original
    assert manifest["sha256"] == hashlib.sha256(payload).hexdigest()
    rows = [json.loads(line) for line in payload.decode("utf-8").splitlines()]
    assert b"\\u" not in payload
    for row in rows:
        digest = hashlib.sha256(row["group_id"].encode("utf-8")).digest()
        assert row["split"] == ("dev" if int.from_bytes(digest[:8], "big") % 10 < 7 else "holdout")
    assert len({row["split"] for row in rows if row["group_id"] == "G-X-001"}) == 1
    assert manifest["case_count"] == 5 and manifest["group_count"] == 2
    assert manifest["counts"]["expected"] == {"abstain": 1, "answer": 4}
    assert manifest["counts"]["family"] == {"gan_mien_vang": 1, "quy_che": 4}
    assert manifest["counts"]["variant"] == {"form": 2, "keyword": 1, "no_diacritics": 1, "slang": 1}
    assert sum(manifest["counts"]["split"].values()) == 5
    assert {runner.split_for_group(f"G-{i}") for i in range(50)} == {"dev", "holdout"}


def test_invalid_merge_is_rejected():
    cases, chunks = fixture()
    cases[0]["gold"] = []
    with pytest.raises(ValueError, match="invalid"):
        runner.merge_cases(cases, chunks)


def test_jsonl_parser_collects_line_errors_and_duplicate_keys(monkeypatch):
    text = '{"case_id":"good"}\n\nnot-json\n{"case_id":"a","case_id":"b"}\n'
    monkeypatch.setattr(Path, "read_text", lambda *a, **kw: text)
    records, errors = runner.read_jsonl(Path("memory.jsonl"))
    assert records == [{"case_id": "good"}]
    assert [error["case_id"] for error in errors] == ["memory.jsonl:3", "memory.jsonl:4"]
    assert all(error["code"] == "INVALID_JSON" for error in errors)


def test_jsonl_read_failure(monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("unreadable")
    monkeypatch.setattr(Path, "read_text", fail)
    assert runner.read_jsonl(Path("memory.jsonl"))[1][0]["code"] == "READ_ERROR"


def memory_inputs(monkeypatch, cases, chunks):
    monkeypatch.setattr(Path, "glob", lambda *a: [Path("memory.jsonl")])
    monkeypatch.setattr(runner, "read_jsonl", lambda path: (chunks if path.name == "served-chunks.jsonl" else cases, []))


@pytest.mark.parametrize("command", ["validate", "stats", "merge"])
def test_cli_commands_and_manifest_in_memory(command, monkeypatch, capsys):
    cases, chunks = fixture()
    memory_inputs(monkeypatch, cases, chunks)
    writes = []
    monkeypatch.setattr(runner, "_write_outputs", lambda *a, **kw: writes.append((a, kw)))
    assert runner.main([command]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["case_count"] == 4 and report["status"] == "ok"
    assert bool(writes) == (command == "merge")
    if writes:
        (output, manifest, payload, saved), options = writes[0]
        assert output.name == "cases.jsonl" and manifest.name == "cases.manifest.json"
        assert saved["sha256"] == hashlib.sha256(payload).hexdigest()
        assert options["force"] is False


def test_cli_stats_explicit_merged_file(monkeypatch, capsys):
    cases, chunks = fixture()
    memory_inputs(monkeypatch, cases, chunks)
    monkeypatch.setattr(Path, "glob", lambda *a: pytest.fail("Explicit --cases must not read shards"))
    assert runner.main(["stats", "--cases", "merged.jsonl"]) == 0
    assert json.loads(capsys.readouterr().out)["group_count"] == 1


@pytest.mark.parametrize("command", ["validate", "merge", "stats"])
def test_cli_reports_case_errors_exits_one_and_never_writes(command, monkeypatch, capsys):
    cases, chunks = fixture()
    cases[0]["gold"] = []
    memory_inputs(monkeypatch, cases, chunks)
    monkeypatch.setattr(runner, "_write_outputs", lambda *a, **kw: pytest.fail("Invalid cases cannot be written"))
    assert runner.main([command]) == 1
    assert f"{cases[0]['case_id']}: ANSWER_WITHOUT_GOLD" in capsys.readouterr().err


def test_cli_fails_on_json_errors_even_with_other_valid_records(monkeypatch, capsys):
    cases, chunks = fixture()
    memory_inputs(monkeypatch, cases, chunks)
    monkeypatch.setattr(runner, "read_jsonl", lambda p: (chunks, []) if p.name == "served-chunks.jsonl"
                        else (cases, [{"case_id": "memory:5", "code": "INVALID_JSON", "message": "bad"}]))
    assert runner.main(["merge"]) == 1
    assert "memory:5: INVALID_JSON" in capsys.readouterr().err


@pytest.mark.parametrize("existing", ["cases.jsonl", "cases.manifest.json"])
def test_either_existing_output_prevents_all_writes_without_force(existing, monkeypatch):
    output = ROOT / "evals/datasets/rag-v2/cases.jsonl"
    manifest = output.with_suffix(".manifest.json")
    monkeypatch.setattr(Path, "exists", lambda path: path.name == existing)
    monkeypatch.setattr(Path, "open", lambda *a, **kw: pytest.fail("Must preflight both outputs"))
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        runner._write_outputs(output, manifest, b"new", {}, inputs=[], force=False)


def test_force_writes_both_payloads_in_memory(monkeypatch):
    output = ROOT / "evals/datasets/rag-v2/cases.jsonl"
    manifest = output.with_suffix(".manifest.json")
    written = {}

    class Sink(BytesIO):
        def close(self):
            written[self.target] = self.getvalue()
            super().close()

    def memory_open(path, mode):
        assert mode == "wb"
        sink = Sink()
        sink.target = path.name
        return sink

    monkeypatch.setattr(Path, "exists", lambda *a: True)
    monkeypatch.setattr(Path, "is_file", lambda *a: True)
    monkeypatch.setattr(Path, "open", memory_open)
    runner._write_outputs(output, manifest, b"payload\n", {"case_count": 4}, inputs=[], force=True)
    assert written["cases.jsonl"] == b"payload\n"
    assert json.loads(written["cases.manifest.json"]) == {"case_count": 4}


@pytest.mark.parametrize("kind", ["outside", "same", "input"])
def test_unsafe_output_paths_fail_before_writing(kind, monkeypatch):
    output = ROOT / "evals/datasets/rag-v2/cases.jsonl"
    manifest = output.with_suffix(".manifest.json")
    if kind == "outside":
        output = ROOT.parent / "outside.jsonl"
    elif kind == "same":
        manifest = output
    monkeypatch.setattr(Path, "open", lambda *a, **kw: pytest.fail("Unsafe outputs must never open"))
    with pytest.raises(ValueError, match="Unsafe|distinct"):
        runner._write_outputs(output, manifest, b"x", {}, inputs=[output] if kind == "input" else [], force=True)
