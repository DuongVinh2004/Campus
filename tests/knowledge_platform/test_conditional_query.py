import pytest

from campus247.application.retrieval.conditional_query import conditional_retrieval_question


@pytest.mark.parametrize("question,expected", [
    ("Nộp hồ sơ muộn thì có tự động bị từ chối trong mọi trường hợp không?", "Điều kiện áp dụng: Nộp hồ sơ muộn; bị từ chối?"),
    ("Không mang thẻ thì có luôn bị từ chối không?", "Điều kiện áp dụng: Không mang thẻ; bị từ chối?"),
    ("Vắng kiểm tra có phép thì có tự động không được thi không?", "Điều kiện áp dụng: Vắng kiểm tra có phép; không được thi?"),
    ("Nop muon thi co tu dong bi tu choi trong moi truong hop khong?", "Điều kiện áp dụng: Nop muon; bi tu choi?"),
])
def test_retrieval_projection_preserves_subject_and_outcome_qualifiers(question, expected):
    assert conditional_retrieval_question(question) == expected


@pytest.mark.parametrize("question", [
    "Nộp hồ sơ cần giấy tờ gì?", "Tôi không muốn bỏ học thì cần làm gì?",
    "Tôi có được tự động gia hạn không?", "Không được nộp muộn có đúng không?",
    "Nộp muộn thì có được tiếp nhận không?", "Nộp muộn thì có tự động bị từ chối không? Tôi cần đến đâu?",
])
def test_other_intents_and_multiple_questions_keep_full_wording(question):
    assert conditional_retrieval_question(question) == question
