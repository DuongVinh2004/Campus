"""F7 through the real HTTP entry: concepts, mastery updated by graded answers, the class map with k >= 5, and the hint ladder."""
import json

import pytest

from campus247.features import runtime
from campus247.ports.llm import LlmResponse, LlmResponseStatus
from test_practice_http import OTHER, QUOTE, published_set, room  # noqa: F401
from test_session_revocation_boundary import call, env  # noqa: F401


LEAD = "Vật liệu được chọn theo loại lực tác dụng lên cấu kiện."


@pytest.fixture(autouse=True)
def pages(room):
    """Page 1 also has a sentence that does not give the answer away, which is what a level 1-2 hint may quote."""
    texts = {1: f"Chương 1. {QUOTE} nhưng chịu kéo kém. {LEAD}", 2: f"Chương 2. {OTHER}."}

    async def extract_page(storage_key, page_no):
        return texts[page_no]

    room.service.blobs.extract_page = extract_page


@pytest.fixture
def flags(monkeypatch):
    on = {"learning.mastery_map": True, "learning.ai_explanations": False}
    monkeypatch.setattr(runtime, "value", lambda key, fallback: on.get(key, fallback))
    return on


def state_of(room):
    return room.client.portal.call(room.service.repository.transaction().__aenter__)


def concept(room, label="Bê tông chịu nén", page=1, **extra):
    body = {"label": label, "links": [{"kind": "PAGE", "target": f"{room.version_id}:{page}"}]} | extra
    return call(room.client, "POST", f"/mastery/offerings/{room.oid}/concepts", room.teacher, json=body)


def enable_tutor(room, revision=0, **fields):
    body = {"revision": revision, "tutor_enabled": True, "reveal_after_attempts": 2, "model_hints_enabled": False} | fields
    return call(room.client, "PUT", f"/tutor/offerings/{room.oid}/settings", room.teacher, json=body)


def answer(room, item_id, choices):
    reply = call(room.client, "POST", f"/practice-items/{item_id}/attempts", room.student, json={"choices": choices})
    assert reply.status_code == 200, reply.text
    return reply.json()


def hint(room, item_id, **body):
    return call(room.client, "POST", f"/tutor/practice-items/{item_id}/hints", room.student, json=body)


# ------------------------------------------------------------------------------------------------ concepts
def test_a_lecturer_writes_concepts_students_read_only_approved_ones(room, flags):
    made = concept(room)
    assert made.status_code == 200, made.text
    assert made.json()["status"] == "APPROVED" and made.json()["origin"] == "LECTURER"
    assert concept(room).status_code == 409                                         # same label
    assert concept(room, "Trang lạ", page=99).status_code == 422                     # page beyond the file
    assert call(room.client, "POST", f"/mastery/offerings/{room.oid}/concepts", room.student, json={"label": "Thử"}).status_code in {403, 404}
    retired = call(room.client, "PATCH", f"/mastery/concepts/{made.json()['id']}", room.teacher, json={"revision": 1, "status": "RETIRED"})
    assert retired.status_code == 200 and retired.json()["status"] == "RETIRED"
    assert call(room.client, "PATCH", f"/mastery/concepts/{made.json()['id']}", room.teacher, json={"revision": 2, "label": "Sửa"}).status_code == 409
    seen = call(room.client, "GET", f"/mastery/offerings/{room.oid}/concepts", room.student).json()
    assert seen["concepts"] == []                                                     # retired is not shown to a student
    staff = call(room.client, "GET", f"/mastery/offerings/{room.oid}/concepts", room.teacher).json()
    assert [c["status"] for c in staff["concepts"]] == ["RETIRED"]


# ------------------------------------------------------------------------------------------------ mastery
def test_a_graded_answer_moves_the_mastery_of_the_concepts_of_its_page(room, flags):
    _, choice_id, short_id = published_set(room)
    page_one = concept(room).json()["id"]
    concept(room, "Thép chịu kéo", page=2)
    first = answer(room, choice_id, ["a"])
    assert first["mastery"] == [{"concept_id": page_one, "band": "NOT_ENOUGH_DATA"}]
    answer(room, choice_id, ["a"])
    answer(room, choice_id, ["a"])
    mine = call(room.client, "GET", f"/mastery/offerings/{room.oid}/me", room.student).json()
    rows = {r["label"]: r for r in mine["concepts"]}
    assert rows["Bê tông chịu nén"]["attempts"] == 3 and rows["Bê tông chịu nén"]["band"] in {"PROGRESSING", "MASTERED"}
    assert rows["Thép chịu kéo"]["attempts"] == 0 and rows["Thép chịu kéo"]["band"] == "NOT_ENOUGH_DATA"
    stored = state_of(room)["concept_mastery"][f"{page_one}:{room.accounts['STUDENT']['subject_id']}"]
    assert stored["model_version"] == "bkt-v1" and stored["attempts"] == 3 and 0.2 < stored["p_known"] <= 1
    assert state_of(room)["practice_attempts"] and all("choices" in a for a in state_of(room)["practice_attempts"].values())


def test_without_the_feature_answers_do_not_touch_mastery(room, flags):
    flags["learning.mastery_map"] = False
    _, choice_id, _ = published_set(room)
    concept(room)
    assert "mastery" not in answer(room, choice_id, ["a"])
    assert not state_of(room).get("concept_mastery")


def test_three_wrong_answers_mark_the_concept_for_review_and_it_is_suggested_first(room, flags):
    _, choice_id, _ = published_set(room)
    concept(room)
    for _ in range(3):
        answer(room, choice_id, ["b"])
    mine = call(room.client, "GET", f"/mastery/offerings/{room.oid}/me", room.student).json()
    assert mine["concepts"][0]["band"] == "NEEDS_REVIEW" and mine["review_first"]["label"] == "Bê tông chịu nén"


# ------------------------------------------------------------------------------------------------ class map (k >= 5)
def test_the_map_is_hidden_for_a_small_class_and_from_students(room, flags):
    _, choice_id, _ = published_set(room)
    concept(room)
    answer(room, choice_id, ["a"])
    assert call(room.client, "GET", f"/mastery/offerings/{room.oid}/map", room.student).status_code in {403, 404}
    small = call(room.client, "GET", f"/mastery/offerings/{room.oid}/map", room.teacher).json()
    assert small["suppressed"] is True and small["concepts"] == [] and small["items"] == [] and small["students"] == "<5"
    csv_text = call(room.client, "GET", f"/mastery/offerings/{room.oid}/map.csv", room.teacher).text
    assert csv_text.splitlines()[1:] == []


def test_the_map_of_a_class_of_six_shows_counts_only_and_hides_small_cells(room, flags):
    _, choice_id, _ = published_set(room)
    cid = concept(room).json()["id"]

    async def add_students(state=None):
        async with room.service.repository.transaction() as s:
            for n in range(6):
                sid = f"synthetic-student-{n}"
                s["members"][f"m-{n}"] = {"id": f"m-{n}", "offering_id": room.oid, "actor_subject_id": sid, "role": "STUDENT", "status": "ACTIVE"}
                # four of six are mastered, two need review: the "needs review" cell (2) is under k and must not show its number
                p, attempts = (0.97, 6) if n < 4 else (0.1, 5)
                s.setdefault("concept_mastery", {})[f"{cid}:{sid}"] = {"concept_id": cid, "student_id": sid, "offering_id": room.oid,
                    "p_known": p, "attempts": attempts, "correct": attempts if n < 4 else 0, "last_attempt_at": "2026-11-26T00:00:00Z", "model_version": "bkt-v1"}
    room.client.portal.call(add_students)
    result = call(room.client, "GET", f"/mastery/offerings/{room.oid}/map", room.teacher)
    assert result.status_code == 200, result.text
    body = result.json()
    row = body["concepts"][0]
    assert body["suppressed"] is False and row["students"] == 7          # six added plus the class's own student
    assert row["bands"]["MASTERED"] == "<5" and row["bands"]["NEEDS_REVIEW"] == "<5"
    assert "synthetic-student" not in json.dumps(body) and room.accounts["STUDENT"]["subject_id"] not in json.dumps(body)
    exported = call(room.client, "GET", f"/mastery/offerings/{room.oid}/map.csv", room.teacher)
    assert exported.headers["content-type"].startswith("text/csv") and "synthetic-student" not in exported.text


# ------------------------------------------------------------------------------------------------ hints
def test_the_tutor_is_off_until_the_lecturer_turns_it_on(room, flags):
    _, choice_id, _ = published_set(room)
    answer(room, choice_id, ["b"])
    refused = hint(room, choice_id)
    assert refused.status_code == 403 and refused.json()["code"] == "TUTOR_DISABLED_FOR_OFFERING"
    assert call(room.client, "PUT", f"/tutor/offerings/{room.oid}/settings", room.student,
                json={"revision": 0, "tutor_enabled": True, "reveal_after_attempts": 2, "model_hints_enabled": False}).status_code in {403, 404}
    assert enable_tutor(room).status_code == 200
    assert enable_tutor(room).status_code == 409                                     # stale revision
    assert hint(room, choice_id).status_code == 200


def test_the_ladder_points_to_the_page_then_narrows_and_opens_the_solution_only_when_allowed(room, flags):
    _, choice_id, _ = published_set(room)
    enable_tutor(room)
    assert hint(room, choice_id).json()["code"] == "NO_WRONG_ATTEMPT"
    answer(room, choice_id, ["b"])
    first = hint(room, choice_id).json()
    assert first["level"] == 1 and first["origin"] == "TEMPLATE" and first["page"] == 1 and first["quote"] == LEAD
    assert "nén" not in (first["hint"] + first["quote"]).casefold()                  # neither the hint nor its quote gives the answer
    early = hint(room, choice_id, solution=True)
    assert early.status_code == 409 and early.json()["code"] == "HINT_LEVEL_NOT_ALLOWED"
    assert hint(room, choice_id, more=True).json()["level"] == 2
    answer(room, choice_id, ["b"])
    solution = hint(room, choice_id, solution=True).json()
    assert solution["level"] == 3 and "Xem trang 1." in solution["hint"]


def test_a_reply_is_kept_only_as_a_hash_and_a_question_has_at_most_six_hints(room, flags):
    _, choice_id, _ = published_set(room)
    enable_tutor(room)
    answer(room, choice_id, ["b"])
    assert hint(room, choice_id, reply="Em nghĩ bê tông chịu kéo tốt").status_code == 200
    turns = list(state_of(room)["tutor_turns"].values())
    assert "Em nghĩ" not in json.dumps(turns, ensure_ascii=False) and len(turns[0]["reply_sha256"]) == 64
    for _ in range(5):
        assert hint(room, choice_id).status_code == 200
    last = hint(room, choice_id)
    assert last.status_code == 429 and last.json()["code"] == "HINT_TURNS_EXHAUSTED"


class Gateway:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0

    async def generate(self, request):
        self.calls += 1
        value = self.replies.pop(0)
        return LlmResponse(LlmResponseStatus.COMPLETED, "fake", "fake", structured_output=value, output_text=json.dumps(value, ensure_ascii=False))


def allow_model(room, flags, replies):
    flags["learning.ai_explanations"] = True
    version = state_of(room)["versions"][room.version_id]
    room.service.ai_source_hashes = frozenset({version["sha256"]})
    room.service.ai_gateway = Gateway(replies)
    enable_tutor(room, model_hints_enabled=True)
    return room.service.ai_gateway


def test_a_model_hint_that_leaks_the_answer_is_retried_once_then_replaced_by_the_template(room, flags):
    _, choice_id, _ = published_set(room)
    gateway = allow_model(room, flags, [{"hint": "Đáp án là Nén.", "quote": QUOTE}, {"hint": "Chọn đáp án a nhé.", "quote": QUOTE}])
    answer(room, choice_id, ["b"])
    result = hint(room, choice_id).json()
    assert gateway.calls == 2 and result["origin"] == "TEMPLATE" and "nén" not in (result["hint"] + result["quote"]).casefold()


def test_a_checked_model_hint_is_shown_with_its_verbatim_quote(room, flags):
    _, choice_id, _ = published_set(room)
    allow_model(room, flags, [{"hint": "Xem lại trang 1: vật liệu này mạnh ở loại lực nào?", "quote": LEAD}])
    answer(room, choice_id, ["b"])
    result = hint(room, choice_id).json()
    assert result["origin"] == "MODEL" and result["quote"] == LEAD and result["remaining_today"] == 29


def test_a_quote_that_gives_the_answer_away_is_refused_like_the_hint(room, flags):
    _, choice_id, _ = published_set(room)
    gateway = allow_model(room, flags, [{"hint": "Đọc lại câu này.", "quote": QUOTE}] * 2)
    answer(room, choice_id, ["b"])
    assert hint(room, choice_id).json()["origin"] == "TEMPLATE" and gateway.calls == 2


def test_a_quote_that_is_not_on_the_page_is_never_shown(room, flags):
    _, choice_id, _ = published_set(room)
    allow_model(room, flags, [{"hint": "Xem lại trang 1.", "quote": "Câu không có trên trang"}] * 2)
    answer(room, choice_id, ["b"])
    assert hint(room, choice_id).json()["origin"] == "TEMPLATE"


def test_without_the_system_ai_feature_no_model_is_called(room, flags):
    _, choice_id, _ = published_set(room)
    gateway = allow_model(room, flags, [{"hint": "x", "quote": QUOTE}])
    flags["learning.ai_explanations"] = False
    answer(room, choice_id, ["b"])
    assert hint(room, choice_id).json()["origin"] == "TEMPLATE" and gateway.calls == 0
