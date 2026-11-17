"""Audit regressions for benefit scope and underspecified exemption questions."""
import pytest
import json
from pathlib import Path

from campus247.rag_v2.understanding.analyze import analyze


@pytest.mark.parametrize("question", [
    "Bố em là công nhân bị tai nạn lao động đang hưởng trợ cấp thường xuyên thì em được giảm bao nhiêu học phí?",
    "Con người hưởng trợ cấp mất sức lao động được giảm học phí bao nhiêu phần trăm?",
    "Sinh viên thuộc hộ nghèo được miễn học phí bao nhiêu?",
    "Mức hỗ trợ chi phí học tập là bao nhiêu?",
    "Hồ sơ giảm học phí phải nộp bao nhiêu bản?",
    "Giam hoc phi cho nguoi khuyet tat la bao nhieu?",
])
def test_benefit_amount_does_not_require_tuition_rate_scope(question):
    result = analyze(question)
    assert result.clarify_prompt is None
    assert not result.required_slots


@pytest.mark.parametrize("question", [
    "Điều kiện để được miễn là gì?", "Em có được miễn không?",
    "Muốn được miễn thì cần những gì?", "Mien can dieu kien gi?",
    "Có những trường hợp được miễn nào?",
])
def test_unspecified_exemption_asks_for_object(question):
    result = analyze(question)
    assert result.question_type == "unclear"
    assert result.clarify_prompt
    assert all(term in result.clarify_prompt for term in ("học phí", "thi", "ngoại ngữ"))


@pytest.mark.parametrize("question", [
    "Điều kiện miễn học phí là gì?", "Điều kiện miễn thi ngoại ngữ?",
    "Ai được miễn học phần GDTC?", "Điều kiện miễn giáo dục quốc phòng?",
])
def test_named_exemption_object_does_not_clarify(question):
    assert analyze(question).clarify_prompt is None


def test_exemption_followup_uses_relevant_history_only():
    result = analyze("Điều kiện để được miễn là gì?", ["Quy định về học phí?"])
    assert result.clarify_prompt is None
    assert "hoc_phi" in result.topics
    assert analyze("Điều kiện để được miễn là gì?", ["Xin chào"]).clarify_prompt


@pytest.mark.parametrize("question", ["Học phí bao nhiêu?", "Mỗi tín chỉ thu bao nhiêu tiền học phí?"])
def test_tuition_rate_still_requires_scope(question):
    assert set(analyze(question).missing_slots) == {"cohort|academic_year", "program"}


@pytest.mark.asyncio
async def test_unspecified_exemption_returns_server_clarification_without_model():
    from campus247.rag_v2.service import RagV2Service
    outcome = await RagV2Service().answer("Điều kiện để được miễn là gì?", (),
        gateway=object(), index=object(), reranker=object(), embed=None)
    assert outcome.kind == "clarify"
    assert outcome.text == analyze("Điều kiện để được miễn là gì?").clarify_prompt


def test_exam_exemption_context_is_retained_without_assuming_tuition():
    result = analyze("Điều kiện để được miễn là gì?", ["Quy định miễn thi ngoại ngữ?"])
    assert result.clarify_prompt is None
    assert "ngoại ngữ" in result.search_query and "học phí" not in result.search_query


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(not (ROOT / "data/rag_v2_index/embedded2/manifest.json").exists(), reason="local audit index absent")
@pytest.mark.asyncio
async def test_school_code_offline_bm25_reaches_packed_parent_context():
    from campus247.rag_v2.adapters.memory_index import MemoryIndex
    from campus247.rag_v2.adapters.runtime import AuthorizedIndex
    from campus247.rag_v2.generation.packing import pack_context
    from campus247.rag_v2.retrieval.hybrid import retrieve
    from campus247.rag_v2.understanding.normalize import normalize_query

    async def no_vector(*args):
        raise RuntimeError("offline probe: vector disabled")

    cases = ROOT / "evals/results/audit-opus-20261101/cases.jsonl"
    case = next(row for line in cases.read_text(encoding="utf-8").splitlines()
                if (row := json.loads(line))["case_id"] == "AU-A12")
    index = MemoryIndex(ROOT / "data/rag_v2_index/embedded2", no_vector)
    rows = {}
    for line in (ROOT / "evals/corpus/served-chunks.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        rows[row["chunk_id"]] = {"content_text": row["text"], "title": row["doc_title"],
            "section_path": row["section_label"], "source_id": row["document_id"],
            "document_version_id": row["version_id"], "page_start": row["page"]}
    view = AuthorizedIndex(index, {uid: index.get(uid) for uid in index.all_ids()}, rows=rows)
    understanding = analyze(case["question"])
    assert "mã trường" in understanding.search_query
    assert "xds" in normalize_query("MÃ TRƯỜNG: XDS")
    gold = {uid for uid in view.all_ids() if any(g["quote"] in view.get(uid).text for g in case["gold"])}
    result = await retrieve(understanding, view, None, rerank_deadline_s=0, final_limit=12)
    assert gold.intersection(c.unit_id for c in result.candidates)
    packed, _ = pack_context((view.get(c.unit_id) for c in result.candidates), view.chunk_unit,
                             budget=19000, max_parents=6)
    assert any(g["quote"] in unit.text for g in case["gold"] for unit in packed.values())


@pytest.mark.parametrize("question", [
    "Trường có cho sinh viên mượn xe đạp miễn phí để đi giữa các cơ sở không?",
    "Wifi thư viện có miễn phí không?",
    "Sinh viên được gửi xe miễn phí ở đâu?",
])
def test_free_of_charge_is_not_an_unspecified_exemption(question):
    assert not analyze(question).clarify_prompt
