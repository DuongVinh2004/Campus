"""Scope names (majors, programmes) come from the documents, and a name no source carries must not make a correct answer unverifiable."""
import json

import pytest
from campus247.rag_v2.ingest.units import extract_scope
from campus247.rag_v2.scope_terms import missing_terms, without_terms
from campus247.rag_v2.service import RagV2Service
from campus247.rag_v2.types import Scope, Unit
from campus247.rag_v2.vocabulary import EMPTY, Vocabulary, initialism

from .test_service import FakeGateway, Reranker, UnitIndex, unit

FEE_TABLE = ("STT | Chương trình đào tạo | Khóa áp dụng | Mức học phí (đồng)/tín chỉ\n"
             "1 | Chương trình đại trà | K68 đến K70 | 610.000")
PRACTICE = "Ngành | Mức học phí thực hành (đồng)/tín chỉ\nTrí tuệ nhân tạo | 650.000"
PROSE = "Học bổng của Công ty ABC dành cho sinh viên ngành Trí tuệ nhân tạo có mức 10.000.000 đồng mỗi năm."


def tabular(text, uid):
    header = text.splitlines()[0]
    body = "\n".join(text.splitlines()[1:])
    return Unit(uid, (f"chunk-{uid}",), "doc", "v", "Quyết định học phí", "khac", "table_row", "Điều 1", 1,
                f"⟦RAG_V2_CONTEXT⟧\nQuyết định học phí\n{header}\n⟦RAG_V2_SOURCE⟧\n{body}", scope=extract_scope(body))


def test_majors_are_read_from_prose_and_from_a_major_column_without_a_list():
    vocabulary = Vocabulary.from_units([unit(PROSE, uid="a" * 16), tabular(PRACTICE, "b" * 16)])
    assert "tri tue nhan tao" in vocabulary.majors
    assert vocabulary.aliases["ttnt"] == "tri tue nhan tao"
    assert initialism("Công nghệ thông tin") == "cntt" and initialism("Cơ khí") == ""


def test_a_question_names_scopes_from_the_vocabulary_or_after_the_word_nganh():
    vocabulary = Vocabulary.from_units([unit(PROSE, uid="a" * 16)])
    assert vocabulary.terms_in("Học bổng TTNT là bao nhiêu?") == ("tri tue nhan tao",)
    assert vocabulary.terms_in("học phí ngành Kiến trúc K70 bao nhiêu") == ("kien truc",)    # unknown to the documents, named outright
    assert vocabulary.terms_in("Học phí K69 là bao nhiêu mỗi tín chỉ?") == ()
    assert EMPTY.terms_in("hoc phi nganh quan ly do thi va cong trinh bao nhieu") == ("quan ly do thi",)
    # "trình" ends a name in "chương trình", but it is part of the name in "công trình" (this cut a major down to "công").
    assert EMPTY.terms_in("Theo kế hoạch học tập của ngành công trình thủy khóa 67 trở đi thì phải học bao nhiêu tín chỉ") == ("cong trinh thuy",)
    assert EMPTY.terms_in("học phí ngành kinh tế chương trình tiên tiến") == ("kinh te",)


def test_a_name_missing_from_the_sources_is_found_and_cut_out_of_the_query():
    fee = tabular(FEE_TABLE, "c" * 16)
    assert missing_terms(["tri tue nhan tao"], [fee], EMPTY) == ["tri tue nhan tao"]
    assert missing_terms(["tri tue nhan tao"], [tabular(PRACTICE, "d" * 16)], EMPTY) == []
    query, shown = without_terms("Học phí ngành Trí tuệ nhân tạo K69 là bao nhiêu?".lower(), ["tri tue nhan tao"])
    assert query == "học phí K69 là bao nhiêu?".replace("K69","k69") and shown == ["trí tuệ nhân tạo"]
    query, _ = without_terms("hoc phi tin chi k68 nganh tri tue nhan tao bao nhieu", ["tri tue nhan tao"])
    assert "tao" not in query and "nganh" not in query and query.startswith("hoc phi tin chi k68")


@pytest.mark.asyncio
async def test_a_table_not_split_by_the_named_major_is_answered_row_by_row_where_the_model_would_refuse():
    first = tabular(FEE_TABLE, "c" * 16)
    second = tabular(FEE_TABLE.replace("610.000", "785.000").replace("Chương trình đại trà", "Chương trình tiên tiến").replace("K68 đến K70", "Từ K69"), "e" * 16)
    gone = tabular(FEE_TABLE.replace("610.000", "575.000").replace("K68 đến K70", "K66"), "f" * 16)
    gateway = FakeGateway(drafts=[[]])   # the model finds nothing it can state
    service = RagV2Service((), Vocabulary.from_units([unit(PROSE, uid="a" * 16)]))
    result = await service.answer("Học phí ngành Trí tuệ nhân tạo K69 là bao nhiêu mỗi tín chỉ?", (), gateway=gateway,
                                  index=UnitIndex([first, second, gone]), reranker=Reranker(), embed=None)
    assert result.kind == "partial"
    assert "610.000" in result.text and "785.000" in result.text and "575.000" not in result.text   # K66 is another cohort
    assert "Chương trình đào tạo: Chương trình đại trà" in result.text
    assert "không nêu riêng cho trí tuệ nhân tạo" in result.preface and "không phân theo trí tuệ nhân tạo" in result.preface


@pytest.mark.asyncio
async def test_a_table_that_is_written_along_the_named_major_is_left_to_the_normal_path():
    practice = tabular(PRACTICE, "d" * 16)
    fee = tabular(FEE_TABLE, "c" * 16)
    gateway = FakeGateway(drafts=[["Ngành Trí tuệ nhân tạo có mức học phí thực hành 650.000 đồng/tín chỉ."]])
    service = RagV2Service((), Vocabulary.from_units([unit(PROSE, uid="a" * 16)]))
    result = await service.answer("Học phí thực hành ngành Trí tuệ nhân tạo bao nhiêu?", (), gateway=gateway,
                                  index=UnitIndex([practice, fee]), reranker=Reranker(), embed=None)
    assert gateway.requests and "650.000" in result.text and "không nêu riêng" not in (result.preface or "")



def titled(title, uid):
    return Unit(uid, (f"chunk-{uid}",), f"doc-{uid}", "v", title, "khac", "curriculum_row", "Học phần", 1,
                f"⟦RAG_V2_CONTEXT⟧\n{title}\n⟦RAG_V2_SOURCE⟧\nHọc phần 381882 – 8 Thực tập tốt nghiệp", scope=Scope())


def test_a_compound_major_from_a_document_title_gets_initialisms_for_each_part_and_expands_the_query():
    from campus247.rag_v2.understanding.analyze import analyze
    vocabulary = Vocabulary.from_units([titled("Kế hoạch giảng dạy CTĐT — Ngành Quản lý xây dựng — Chuyên ngành Kinh tế và Quản lý đô thị (K71QD)", "d" * 16)])
    assert "kinh te va quan ly do thi" in vocabulary.majors and "quan ly xay dung" in vocabulary.majors
    assert vocabulary.aliases["qldt"] == "kinh te va quan ly do thi"
    understood = analyze("K69 QLĐT TTTN ĐATN TC", (), vocabulary)
    assert "kinh te va quan ly do thi" in understood.search_query and understood.scope_terms == ("kinh te va quan ly do thi",)
    assert analyze("Học phí K71 bao nhiêu?", (), vocabulary).search_query.count("kinh te") == 0     # nothing added without an initialism


def test_an_initialism_two_majors_share_is_dropped():
    vocabulary = Vocabulary.from_units([titled("Kế hoạch — Chuyên ngành Kinh tế và Quản lý đô thị", "e" * 16),
                                        titled("Kế hoạch — Chuyên ngành Quy hoạch và Quản lý đô thị", "f" * 16)])
    assert "qldt" not in vocabulary.aliases and vocabulary.expand("QLĐT K71") == ""
