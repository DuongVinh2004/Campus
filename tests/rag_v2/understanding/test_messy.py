import json

import pytest
from campus247.ports.llm import LlmResponse, LlmResponseStatus
from campus247.rag_v2.generation.rewrite import clean_question
from campus247.rag_v2.understanding.analyze import analyze
from campus247.rag_v2.understanding.messy import looks_messy, safe_clean


@pytest.mark.parametrize(("question", "messy"), [
    ("hoc phi k67 bao nhieu mot tin chi", True),                       # no diacritics
    ("Ad ơi em lo quá, em nghe nói có thông báo mới mà em không rõ lắm em nên làm gì bây giờ nữa, "
     "em sợ lỡ hạn nộp hồ sơ lắm, mong ad chỉ giúp em với, em cảm ơn ad nhiều", True),   # rambling
    ("cái vụ ấy là sao vậy bạn", True),                                # nothing recognisable
    ("Học phí K67 bao nhiêu một tín chỉ?", False),                      # clean, topic known
    ("Xin chào", False), ("Thời tiết hôm nay thế nào", False),
])
def test_looks_messy(question, messy):
    u = analyze(question, ())
    assert looks_messy(question, u.topics, u.question_type) is messy


@pytest.mark.parametrize(("question", "cleaned", "ok"), [
    ("hoc phi k67 bao nhieu", "Học phí K67 bao nhiêu?", True),
    ("hoc phi k67 bao nhieu", "Học phí K68 bao nhiêu?", False),                 # changed cohort
    ("hoc phi k67 bao nhieu", "Học phí bao nhiêu?", False),                     # dropped cohort
    ("hoc phi 580.500 co dung ko", "Học phí 580.500 có đúng không?", True),
    ("hoc phi 580.500 co dung ko", "Học phí 585.000 có đúng không?", False),    # invented number
    ("sv khong duoc thi lai a", "Sinh viên không được thi lại à?", True),
    ("sv khong duoc thi lai a", "Sinh viên được thi lại à?", False),            # negation dropped
    ("hoc phi k67", "Xem tại https://x.vn học phí K67", False),                  # link
])
def test_safe_clean_keeps_every_number_code_and_negation(question, cleaned, ok):
    assert safe_clean(question, cleaned) is ok


class Gateway:
    def __init__(self, value=None, status=LlmResponseStatus.COMPLETED, error=None):
        self.value, self.status, self.error, self.requests = value, status, error, []

    async def generate(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return LlmResponse(self.status, "fake", "fake", structured_output=self.value, output_text=json.dumps(self.value))


@pytest.mark.asyncio
async def test_clean_question_returns_the_safe_restatement():
    gateway = Gateway({"question": "Học phí K67 bao nhiêu một tín chỉ?"})
    assert await clean_question(gateway, "hp k67 bn 1 tc", deadline_ms=2000) == "Học phí K67 bao nhiêu một tín chỉ?"
    assert gateway.requests[0].request_id == "rag_v2_rewrite"


@pytest.mark.asyncio
@pytest.mark.parametrize("gateway", [
    Gateway({"question": "Học phí K70 bao nhiêu?"}), Gateway({"question": 5}), Gateway(None),
    Gateway({"question": "x"}), Gateway(error=TimeoutError()), Gateway({"question": "ok"}, LlmResponseStatus.FAILED)])
async def test_clean_question_falls_back_to_none(gateway):
    assert await clean_question(gateway, "hp k67 bn", deadline_ms=2000) is None


@pytest.mark.asyncio
async def test_clean_question_needs_time_and_text():
    gateway = Gateway({"question": "Học phí K67?"})
    assert await clean_question(gateway, "hp k67", deadline_ms=100) is None
    assert await clean_question(gateway, "   ", deadline_ms=2000) is None
    assert not gateway.requests
