from datetime import UTC, datetime

import pytest

from campus247.application.knowledge.curriculum_geometry import geometry_allows, geometry_scopes
from campus247.application.knowledge.platform_models import PlatformError, digest
from campus247.application.knowledge.source_snapshot import PROCESSOR, scope_allows, validate_snapshot


def fixture():
    header = {"row": 0, "column": 0, "bbox": [0, 0, 100, 10], "text": "Học kỳ 1"}
    native = {"row": 1, "column": 0, "bbox": [0, 10, 100, 30], "text": "123456 – 3\nMôn A"}
    cell = {**native, "id": "a", "page": 1, "table": 0, "header": header,
        "semester": 1, "semester_header": "Học kỳ 1", "course_codes": ["123456"],
        "text_sha256": digest(native["text"].encode())}
    witness = {"schema": "reviewed-curriculum-geometry-v1", "reviewed": True, "original_sha256": "a"*64,
        "programme_code": "71TEST", "cells": [cell], "edges": [], "ambiguous_course_cells": [],
        "geometry_pages": {"1": {"tables": [{"rows": [[header], [native]]}], "shapes": []}}}
    text = "71TEST\nHọc kỳ 1\n"+native["text"]
    extracted = {"original_sha256": "a"*64, "curriculum_geometry": witness,
        "blocks": [{"block_id": "0", "page": 1, "text": text, "geometry_binding": {"kind": "cell", "id": "a"}}]}
    now = datetime(2026, 10, 25, tzinfo=UTC)
    rendition = {"processor": PROCESSOR, "original_sha256": "a"*64, "issues": [],
        "applicability": {"kind": "COHORT_SNAPSHOT", "cohorts": ["K71"], "reviewed_at": now.isoformat(),
            "legal_effective_from": None, "admission_only": True, "geometry_witness_sha256": digest(witness)},
        "pages": [{"block_id": "0", "page": 1, "char_start": 0, "char_end": len(text),
            "text": text, "text_sha256": digest(text.encode())}]}
    return rendition, extracted, now


def test_reviewed_semester_does_not_authorize_a_different_semester_or_unverified_relation():
    rendition, extracted, _ = fixture()
    caps, parents = geometry_scopes(rendition, extracted)
    scope = {**rendition["applicability"], "_verified_geometry": caps}
    assert scope_allows("K71 học kỳ 1 có môn nào?", scope)
    for query in ("K70 học kỳ 1?", "K71 học kỳ 2?", "K71TEST K70 học kỳ 1?",
            "Môn nào là tiên quyết?", "Môn nào song hành?", "Học kỳ I?", "Học kỳ 1 môn 999999?", "Môn 999999 có mấy tín chỉ?"):
        assert not scope_allows(query, scope)
    assert not scope_allows("K71 học kỳ 1?", rendition["applicability"])
    assert parents[rendition["pages"][0]["text_sha256"]] == caps | {"unlabelled_credits": False, "evidence_kind": "cell"}


def test_one_cell_never_authorizes_a_whole_semester_roster_but_a_group_can_answer_its_own_options():
    caps = {"semesters": [5], "course_codes": ["123456", "234567"], "relation_types": [], "evidence_kind": "cell"}
    assert not geometry_allows("Học kỳ 5 có những học phần nào?", caps)
    assert not geometry_allows("Học kỳ 5 gồm những gì?", caps)
    assert not geometry_allows("Học kỳ 5 tất cả các môn kể cả tự chọn?", caps)
    assert geometry_allows("Học kỳ 5 nhóm tự chọn ghi các môn nào?", caps)
    assert geometry_allows("Học kỳ 5 mã 123456 có tên gì?", caps)
    assert geometry_allows("Học kỳ 5 có những học phần nào?", {**caps, "evidence_kind": "semester"})


def test_one_matching_programme_cannot_admit_a_second_unproved_programme():
    rendition, extracted, _ = fixture()
    caps, _ = geometry_scopes(rendition, extracted)
    scope = {**rendition["applicability"], "programme_codes": ["71TEST"], "_verified_geometry": caps}
    assert scope_allows("K71TEST học kỳ 1?", scope)
    assert not scope_allows("K71TEST và K71KHAC học kỳ 1?", scope)


def test_edited_semester_cannot_reuse_the_original_cell_geometry_even_with_a_rehashed_manifest():
    rendition, extracted, _ = fixture()
    extracted["curriculum_geometry"]["cells"][0]["semester"] = 2
    rendition["applicability"]["geometry_witness_sha256"] = digest(extracted["curriculum_geometry"])
    with pytest.raises(PlatformError, match="CURRICULUM_COLUMN_BINDING"):
        geometry_scopes(rendition, extracted)


def test_geometry_witness_digest_and_private_runtime_capability_cannot_be_forged_in_stored_scope():
    rendition, extracted, now = fixture()
    rendition["applicability"]["geometry_witness_sha256"] = "0"*64
    with pytest.raises(PlatformError, match="CURRICULUM_GEOMETRY_BINDING"):
        geometry_scopes(rendition, extracted)
    rendition, extracted, now = fixture()
    rendition["applicability"]["_verified_geometry"] = {"semesters": [1, 2]}
    with pytest.raises(PlatformError, match="SNAPSHOT_BINDING_REQUIRED"):
        validate_snapshot(rendition, extracted, original_sha256="a"*64, effective_from=now)


def test_credit_numbers_in_unlabelled_pe_names_and_unknown_relation_types_remain_blocked():
    caps = {"semesters": [1], "relation_types": ["PREREQUISITE"], "course_codes": ["123456"], "unlabelled_credits": True}
    assert not geometry_allows("Học kỳ 1 GD thể chất 2 có 2 tín chỉ?", caps)
    assert not geometry_allows("Học phần học trước của 123456?", caps)
    assert not geometry_allows("Điều kiện để học 123456?", caps)
    assert not geometry_allows("Song hành với 123456?", caps)
    assert not geometry_allows("Nhóm tự chọn 1 phải chọn mấy môn?", caps)
    assert not geometry_allows("Nhóm tự chọn 1 có phải chọn 1 môn không?", caps)


def test_semester_parent_keeps_the_complete_reviewed_roster_and_unlabelled_credit_boundaries():
    rendition, extracted, _ = fixture()
    witness = extracted["curriculum_geometry"]
    physical = {**witness["cells"][0], "id": "pe", "row": 2, "bbox": [0, 30, 100, 50],
        "text": "GD thể chất 2", "text_sha256": digest("GD thể chất 2".encode()),
        "course_codes": [], "unlabelled_credits": True}
    witness["cells"].append(physical)
    witness["geometry_pages"]["1"]["tables"][0]["rows"].append([
        {k: physical[k] for k in ("row", "column", "bbox", "text")}])
    witness["printed_total"] = "Tổng: 3TC"
    witness["semester_groups"] = [{"id": "s1", "semester": 1, "cell_ids": ["a", "pe"]}]
    block = extracted["blocks"][0]
    block["geometry_binding"] = {"kind": "semester", "id": "s1"}
    block["text"] = "71TEST\nHọc kỳ 1\n123456 – 3\nMôn A\n\nGD thể chất 2\nTổng: 3TC"
    rendition["pages"][0].update(text=block["text"], char_end=len(block["text"]), text_sha256=digest(block["text"].encode()))
    rendition["applicability"]["geometry_witness_sha256"] = digest(witness)
    caps, _ = geometry_scopes(rendition, extracted)
    assert geometry_allows("Học kỳ 1 môn 123456 bao nhiêu tín chỉ?", caps)
    assert geometry_allows("Học kỳ 1 GD thể chất 2 có trong danh sách không?", caps)
    assert not geometry_allows("Học kỳ 1 GD thể chất 3 có trong danh sách không?", caps)
    assert not geometry_allows("GD thể chất 2 có 2 tín chỉ?", caps)
    witness["semester_groups"][0]["cell_ids"] = ["a"]
    rendition["applicability"]["geometry_witness_sha256"] = digest(witness)
    with pytest.raises(PlatformError, match="CURRICULUM_SEMESTER_BINDING"):
        geometry_scopes(rendition, extracted)


@pytest.mark.parametrize("other_name,ambiguous", [("Môn B", True), ("Môn A", False)])
def test_duplicate_printed_code_is_derived_from_distinct_printed_variants(other_name, ambiguous):
    rendition, extracted, _ = fixture()
    witness = extracted["curriculum_geometry"]
    original = witness["cells"][0]
    second = {**original, "id": "b", "row": 2, "bbox": [0, 30, 100, 50],
        "text": "123456 – 3\n"+other_name, "text_sha256": digest(("123456 – 3\n"+other_name).encode())}
    witness["cells"].append(second)
    witness["geometry_pages"]["1"]["tables"][0]["rows"].append([
        {k: second[k] for k in ("row", "column", "bbox", "text")}])
    rendition["applicability"]["geometry_witness_sha256"] = digest(witness)
    caps, parents = geometry_scopes(rendition, extracted)
    assert caps["ambiguous_course_codes"] == (["123456"] if ambiguous else [])
    assert geometry_allows("Học kỳ 1 có những học phần nào?", caps)
    for query in ("Môn 123456 có tên duy nhất là gì?", "Môn 123456 có bao nhiêu tín chỉ?"):
        assert geometry_allows(query, caps) is not ambiguous
        assert geometry_allows(query, parents[rendition["pages"][0]["text_sha256"]]) is not ambiguous
