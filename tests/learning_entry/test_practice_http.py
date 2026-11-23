"""Practice questions through the real HTTP entry: who may write, what a student sees before and after answering, the citation
check at publication, spaced review, idempotent answers, and the class statistics that stay hidden for a small class."""
import pytest
from fastapi.testclient import TestClient  # noqa: F401  (the env fixture builds the client)

from test_session_revocation_boundary import Class, call, env, make_pdf  # noqa: F401

QUOTE = "Bê tông cốt thép chịu nén tốt"
OTHER = "Thép chịu kéo rất tốt"


@pytest.fixture
def room(env):
    lifecycle = env[0]
    room = Class(lifecycle)
    material = room.material()
    room.version_id = room.upload_and_publish(material["id"], make_pdf(2))
    room.service.practice_offerings = frozenset({room.oid})
    texts = {1: f"Chương 1. {QUOTE} nhưng chịu kéo kém.", 2: f"Chương 2. {OTHER}."}

    async def extract_page(storage_key, page_no):
        return texts[page_no]

    room.service.blobs.extract_page = extract_page
    return room


def make_set(room, title="Ôn tập chương 1"):
    reply = call(room.client, "POST", f"/sessions/{room.sid}/practice-sets", room.teacher, json={"version_id": room.version_id, "title": title})
    assert reply.status_code == 200, reply.text
    return reply.json()


def add_item(room, set_id, revision, **fields):
    body = {"revision": revision, "kind": "single_choice", "prompt": "Bê tông chịu lực nào tốt?",
            "options": [{"id": "a", "text": "Nén"}, {"id": "b", "text": "Kéo"}], "answer": ["a"], "explanation": "Xem trang 1.",
            "citations": [{"page_no": 1, "quote": QUOTE}]} | fields
    return call(room.client, "PUT", f"/practice-sets/{set_id}/items", room.teacher, json=body)


def publish(room, set_id, revision):
    return call(room.client, "POST", f"/practice-sets/{set_id}/publication", room.teacher, json={"revision": revision})


def published_set(room):
    row = make_set(room)
    item = add_item(room, row["id"], row["revision"])
    assert item.status_code == 200, item.text
    short = add_item(room, row["id"], item.json()["set_revision"], kind="short_answer", prompt="Vật liệu nào chịu kéo tốt?", options=[], answer=[],
                     accepted=["thép", "Thép xây dựng"], citations=[{"page_no": 2, "quote": OTHER}])
    assert short.status_code == 200, short.text
    done = publish(room, row["id"], short.json()["set_revision"])
    assert done.status_code == 200, done.text
    return row["id"], item.json()["id"], short.json()["id"]


def test_the_feature_is_off_until_a_class_is_switched_on(env):
    room = Class(env[0])
    material = room.material()
    version = room.upload_and_publish(material["id"], make_pdf())
    reply = call(room.client, "POST", f"/sessions/{room.sid}/practice-sets", room.teacher, json={"version_id": version, "title": "x"})
    assert reply.status_code in {403, 404}


def test_a_lecturer_builds_publishes_and_a_student_sees_questions_without_answers(room):
    set_id, choice_id, _ = published_set(room)
    staff = call(room.client, "GET", f"/practice-sets/{set_id}", room.teacher).json()
    assert staff["status"] == "PUBLISHED" and staff["items"][0]["answer"] == ["a"]
    seen = call(room.client, "GET", f"/practice-sets/{set_id}", room.student).json()
    flat = str(seen)
    assert [i["kind"] for i in seen["items"]] == ["single_choice", "short_answer"]
    assert all(set(i) == {"id", "kind", "prompt", "options"} for i in seen["items"])
    assert "Xem trang 1" not in flat and QUOTE not in flat and "thép" not in flat.casefold()


def test_students_cannot_write_and_other_students_cannot_read_a_draft(room):
    row = make_set(room)
    assert call(room.client, "POST", f"/sessions/{room.sid}/practice-sets", room.student, json={"version_id": room.version_id, "title": "x"}).status_code in {403, 404}
    assert call(room.client, "GET", f"/practice-sets/{row['id']}", room.student).status_code == 404  # still a draft
    assert call(room.client, "GET", f"/sessions/{room.sid}/practice-sets", room.student).json()["items"] == []


def test_a_quote_that_is_not_on_its_page_stops_publication_and_nothing_changes(room):
    row = make_set(room)
    ok = add_item(room, row["id"], row["revision"])
    bad = add_item(room, row["id"], ok.json()["set_revision"], citations=[{"page_no": 2, "quote": "Câu này không có trong trang hai"}])
    refused = publish(room, row["id"], bad.json()["set_revision"])
    assert refused.status_code == 422 and refused.json()["code"] == "CITATIONS_NOT_ON_PAGE"
    assert call(room.client, "GET", f"/practice-sets/{row['id']}", room.teacher).json()["status"] == "DRAFT"


@pytest.mark.parametrize("fields", [
    {"options": [{"id": "a", "text": "Nén"}], "answer": ["a"]},                                  # one option
    {"answer": ["z"]},                                                                           # answer is not an option
    {"answer": ["a", "b"]},                                                                      # two answers for single choice
    {"citations": [{"page_no": 9, "quote": QUOTE}]},                                             # page beyond the file
    {"kind": "short_answer", "options": [], "answer": [], "accepted": []},                       # nothing accepted
])
def test_malformed_questions_are_refused(room, fields):
    row = make_set(room)
    assert add_item(room, row["id"], row["revision"], **fields).status_code == 422


def test_a_published_set_cannot_be_edited_and_a_stale_revision_conflicts(room):
    set_id, *_ = published_set(room)
    assert add_item(room, set_id, 99).status_code == 409
    row = make_set(room, "Bộ hai")
    assert add_item(room, row["id"], row["revision"] + 5).status_code == 409


def test_answering_grades_exactly_returns_the_explanation_and_schedules_a_review(room):
    set_id, choice_id, short_id = published_set(room)
    right = call(room.client, "POST", f"/practice-items/{choice_id}/attempts", room.student, json={"choices": ["a"]}).json()
    assert right["correct"] is True and right["explanation"] == "Xem trang 1." and right["citations"][0]["page_no"] == 1 and right["next_review_at"]
    wrong = call(room.client, "POST", f"/practice-items/{choice_id}/attempts", room.student, json={"choices": ["b"]}).json()
    assert wrong["correct"] is False
    spelled = call(room.client, "POST", f"/practice-items/{short_id}/attempts", room.student, json={"text": "  THÉP. "}).json()
    assert spelled["correct"] is True
    assert call(room.client, "POST", f"/practice-items/{short_id}/attempts", room.student, json={"text": "gỗ"}).json()["correct"] is False


def test_an_answer_needs_a_valid_choice_and_only_students_answer(room):
    _, choice_id, _ = published_set(room)
    assert call(room.client, "POST", f"/practice-items/{choice_id}/attempts", room.student, json={"choices": ["zzz"]}).status_code == 422
    assert call(room.client, "POST", f"/practice-items/{choice_id}/attempts", room.student, json={}).status_code == 422
    assert call(room.client, "POST", f"/practice-items/{choice_id}/attempts", room.teacher, json={"choices": ["a"]}).status_code in {403, 404}


def test_the_same_idempotency_key_counts_one_attempt(room):
    set_id, choice_id, _ = published_set(room)
    key = {"Idempotency-Key": "k" * 20}
    first = room.client.post(f"/v1/learning/practice-items/{choice_id}/attempts", headers=room.student | key, json={"choices": ["a"]})
    again = room.client.post(f"/v1/learning/practice-items/{choice_id}/attempts", headers=room.student | key, json={"choices": ["a"]})
    assert first.status_code == again.status_code == 200 and first.json() == again.json()
    state = room.client.portal.call(room.service.repository.transaction().__aenter__)
    assert sum(1 for a in state["practice_attempts"].values() if a["item_id"] == choice_id) == 1


def test_the_session_puts_unanswered_questions_first_then_those_due(room):
    set_id, choice_id, short_id = published_set(room)
    call(room.client, "POST", f"/practice-items/{choice_id}/attempts", room.student, json={"choices": ["a"]})
    session = call(room.client, "GET", f"/practice-sets/{set_id}/session", room.student).json()
    assert [i["id"] for i in session["items"]] == [short_id, choice_id]  # never answered first; the answered one is due in days


def test_the_instructor_cannot_open_a_student_session_and_stats_are_hidden_for_a_small_class(room):
    set_id, choice_id, _ = published_set(room)
    call(room.client, "POST", f"/practice-items/{choice_id}/attempts", room.student, json={"choices": ["a"]})
    assert call(room.client, "GET", f"/practice-sets/{set_id}/session", room.teacher).status_code in {403, 404}
    assert call(room.client, "GET", f"/practice-sets/{set_id}/stats", room.student).status_code in {403, 404}
    stats = call(room.client, "GET", f"/practice-sets/{set_id}/stats", room.teacher).json()
    assert stats["suppressed"] is True and stats["items"] == [] and stats["students"] < 5


def test_the_class_page_reports_the_capability(room):
    assert call(room.client, "GET", f"/offerings/{room.oid}", room.student).json()["capabilities"]["practice"] is True
