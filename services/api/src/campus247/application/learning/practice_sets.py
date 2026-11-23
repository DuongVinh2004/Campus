"""Practice questions written by a lecturer for one session's lecture file, and a student's spaced review of them.

Every question cites the page of the file it comes from, and the quote must appear on that page (checked at publication by
`practice.verify_item_citations`). Answers are graded by exact rules, never by a model. A student sees the answer, the explanation
and the citation only after answering. The class statistics are counts; with fewer than MIN_CLASS_FOR_STATS students nothing per
question is shown, because a handful of answers would point at people.

State collections (the same free-form state the other learning features use): practice_sets, practice_items, practice_attempts,
practice_reviews.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from campus247.application.learning.practice import (
    ReviewState,
    grade_choice,
    grade_short_answer,
    next_review,
    pick_session,
    verify_item_citations,
)
from campus247.domain.learning import LearningError, require
from campus247.domain.shared.values import generate_uuid7

PRACTICE_COLLECTIONS = ("practice_sets", "practice_items", "practice_attempts", "practice_reviews")  # PostgreSQL: migration 0032
PRACTICE_READS = {"practice_sets", "practice_set", "practice_session", "practice_stats"}
PRACTICE_WRITES = {"practice-set-create", "practice-item-save", "practice-set-publish", "practice-attempt-save"}
KINDS = ("single_choice", "multi_choice", "short_answer")
MIN_CLASS_FOR_STATS = 5
SESSION_SIZE = 10
MAX_ITEMS_PER_SET = 50


def practice_clock() -> datetime:
    return datetime.now(UTC)


def _stamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class LearningPractice:
    # ------------------------------------------------------------------------------------------------ access
    def practice_session_access(self, state, actor, session_id, *, manage=False):
        session = state["sessions"].get(session_id)
        require(session is not None)
        offering, member = self.access(state, actor, session["offering_id"], write=manage)
        require(offering["id"] in self.practice_offerings)
        return session, offering, member

    def practice_set_access(self, state, actor, set_id, *, manage=False):
        row = state.get("practice_sets", {}).get(set_id)
        require(row is not None)
        session, offering, member = self.practice_session_access(state, actor, row["session_id"], manage=manage)
        require(row["offering_id"] == offering["id"])
        if member["role"] == "STUDENT":
            require(row["status"] == "PUBLISHED")
        return row, session, offering, member

    def practice_items_of(self, state, set_id):
        return sorted((i for i in state.get("practice_items", {}).values() if i["set_id"] == set_id), key=lambda i: (i["ordinal"], i["id"]))

    # ------------------------------------------------------------------------------------------------ views
    @staticmethod
    def practice_item_for_student(item):
        return {"id": item["id"], "kind": item["kind"], "prompt": item["prompt"], "options": item["options"]}

    @staticmethod
    def practice_item_for_staff(item):
        return {key: item[key] for key in ("id", "ordinal", "kind", "prompt", "options", "answer", "accepted", "explanation", "citations", "revision")}

    @staticmethod
    def practice_set_view(row, items=None):
        view = {key: row[key] for key in ("id", "session_id", "version_id", "title", "status", "revision")}
        if items is not None:
            view["items"] = items
        return view

    def read_practice(self, state, actor, kind, target):
        now = practice_clock()
        if kind == "practice_sets":
            _, _, member = self.practice_session_access(state, actor, target)
            staff = member["role"] == "INSTRUCTOR"
            return [self.practice_set_view(row) | {"item_count": len(self.practice_items_of(state, row["id"]))}
                    for _, row in sorted(state.get("practice_sets", {}).items(), reverse=True)
                    if row["session_id"] == target and (staff or row["status"] == "PUBLISHED")]
        row, session, offering, member = self.practice_set_access(state, actor, target)
        staff = member["role"] == "INSTRUCTOR"
        if kind == "practice_set":
            items = self.practice_items_of(state, target)
            return self.practice_set_view(row, [self.practice_item_for_staff(i) if staff else self.practice_item_for_student(i) for i in items])
        if kind == "practice_session":
            require(not staff)
            require(self.feedback_public_source(state, session, row["version_id"]), 409, "SOURCE_UNAVAILABLE", "Tài liệu của bộ câu hỏi không còn khả dụng.")
            items = {i["id"]: i for i in self.practice_items_of(state, target)}
            reviews = state.get("practice_reviews", {})
            states = {}
            for item_id in items:
                review = reviews.get(f"{item_id}:{actor.subject_id}")
                states[item_id] = ReviewState(review["ease"], review["interval_days"], review["repetitions"],
                                              datetime.fromisoformat(review["due_at"]) if review.get("due_at") else None) if review else ReviewState()
            picked = pick_session(states, now=now, size=SESSION_SIZE)
            return self.practice_set_view(row, [self.practice_item_for_student(items[i]) for i in picked])
        require(kind == "practice_stats" and staff)
        students = sum(m["offering_id"] == offering["id"] and m["status"] == "ACTIVE" and m["role"] == "STUDENT" for m in state["members"].values())
        if students < MIN_CLASS_FOR_STATS:
            return {"set_id": target, "students": students, "suppressed": True, "items": []}
        attempts = [a for a in state.get("practice_attempts", {}).values() if a["set_id"] == target]
        result = []
        for item in self.practice_items_of(state, target):
            mine = [a for a in attempts if a["item_id"] == item["id"]]
            result.append({"item_id": item["id"], "prompt": item["prompt"], "attempts": len(mine), "students": len({a["student_id"] for a in mine}),
                           "correct_rate": round(sum(a["correct"] for a in mine) / len(mine), 3) if mine else None})
        return {"set_id": target, "students": students, "suppressed": False, "items": result}

    # ------------------------------------------------------------------------------------------------ writes
    def authorize_practice_action(self, state, actor, action, target):
        if action == "practice-set-create":
            self.practice_session_access(state, actor, target, manage=True)
        elif action == "practice-attempt-save":
            item = state.get("practice_items", {}).get(target)
            require(item is not None)
            _, _, _, member = self.practice_set_access(state, actor, item["set_id"])
            require(member["role"] == "STUDENT")
        else:
            self.practice_set_access(state, actor, target, manage=True)

    @staticmethod
    def check_practice_item(payload, page_count):
        kind = payload["kind"]
        require(kind in KINDS, 422, "INVALID_KIND", "Loại câu hỏi không hợp lệ.")
        options = [{"id": str(o["id"]), "text": str(o["text"]).strip()} for o in payload.get("options", [])]
        answer, accepted = list(payload.get("answer", [])), [str(a).strip() for a in payload.get("accepted", [])]
        if kind == "short_answer":
            require(not options and not answer and 1 <= len(accepted) <= 5 and all(accepted), 422, "INVALID_ANSWER", "Câu trả lời ngắn cần 1 đến 5 đáp án chấp nhận.")
        else:
            ids = [o["id"] for o in options]
            require(2 <= len(options) <= 6 and len(set(ids)) == len(ids) and all(o["text"] for o in options), 422, "INVALID_OPTIONS", "Cần từ 2 đến 6 lựa chọn khác nhau.")
            require(not accepted and set(answer) <= set(ids) and len(set(answer)) == len(answer) and bool(answer), 422, "INVALID_ANSWER", "Đáp án phải là lựa chọn có sẵn.")
            require(kind == "multi_choice" or len(answer) == 1, 422, "INVALID_ANSWER", "Câu một lựa chọn chỉ có một đáp án đúng.")
        citations = [{"page_no": c["page_no"], "quote": str(c["quote"]).strip()} for c in payload["citations"]]
        require(1 <= len(citations) <= 3 and all(1 <= c["page_no"] <= max(page_count, 1) for c in citations), 422, "INVALID_CITATION", "Mỗi câu cần 1 đến 3 trích dẫn đúng trang của tài liệu.")
        return {"kind": kind, "prompt": payload["prompt"].strip(), "options": options, "answer": answer, "accepted": accepted,
                "explanation": payload.get("explanation", "").strip(), "citations": citations}

    def command_practice(self, state, actor, action, target, payload, supplied):
        now = practice_clock()
        if action == "practice-set-create":
            session, offering, _ = self.practice_session_access(state, actor, target, manage=True)
            require(self.feedback_public_source(state, session, payload["version_id"]), 422, "INVALID_SOURCE", "Chọn tệp đã công bố của buổi học.")
            version = state["versions"][payload["version_id"]]
            identifier = generate_uuid7()
            row = {"id": identifier, "session_id": target, "offering_id": offering["id"], "version_id": version["id"], "material_id": version["material_id"],
                   "title": payload["title"].strip(), "status": "DRAFT", "revision": 1, "created_by": actor.subject_id, "created_at": _stamp(now)}
            state.setdefault("practice_sets", {})[identifier] = row
            return self.practice_set_view(row)

        if action == "practice-attempt-save":
            item = state["practice_items"][target]
            row, session, _, _ = self.practice_set_access(state, actor, item["set_id"])
            require(self.feedback_public_source(state, session, row["version_id"]), 409, "SOURCE_UNAVAILABLE", "Tài liệu của bộ câu hỏi không còn khả dụng.")
            if item["kind"] == "short_answer":
                require(isinstance(payload.get("text"), str) and payload["text"].strip() and not payload.get("choices"), 422, "INVALID_ANSWER", "Nhập câu trả lời.")
                correct = grade_short_answer(payload["text"], item["accepted"])
            else:
                chosen = list(payload.get("choices") or [])
                require(bool(chosen) and set(chosen) <= {o["id"] for o in item["options"]} and not payload.get("text"), 422, "INVALID_ANSWER", "Chọn đáp án.")
                correct = grade_choice(chosen, item["answer"])
            attempt_id = generate_uuid7()
            state.setdefault("practice_attempts", {})[attempt_id] = {"id": attempt_id, "item_id": item["id"], "set_id": row["id"], "offering_id": row["offering_id"],
                                                                    "student_id": actor.subject_id, "correct": correct, "at": _stamp(now)}
            key = f"{item['id']}:{actor.subject_id}"
            old = state.setdefault("practice_reviews", {}).get(key)
            previous = ReviewState(old["ease"], old["interval_days"], old["repetitions"], datetime.fromisoformat(old["due_at"])) if old else ReviewState()
            following = next_review(previous, correct=correct, now=now)
            state["practice_reviews"][key] = {"ease": following.ease, "interval_days": following.interval_days, "repetitions": following.repetitions,
                                              "due_at": _stamp(following.due_at)}
            return {"correct": correct, "answer": item["answer"], "accepted": item["accepted"] if item["kind"] == "short_answer" else [],
                    "explanation": item["explanation"], "citations": item["citations"], "next_review_at": _stamp(following.due_at)}

        row, session, offering, _ = self.practice_set_access(state, actor, target, manage=True)
        require(row["status"] == "DRAFT", 409, "INVALID_SET_STATE", "Chỉ sửa bộ câu hỏi còn là bản nháp.")
        require(row["revision"] == payload["revision"], 409, "REVISION_CONFLICT", "Bộ câu hỏi đã thay đổi.")
        version = state["versions"][row["version_id"]]
        if action == "practice-item-save":
            fields = self.check_practice_item(payload, version.get("page_count", 0))
            items = self.practice_items_of(state, target)
            if payload.get("item_id"):
                item = state["practice_items"].get(payload["item_id"])
                require(item is not None and item["set_id"] == target, 404, "NOT_FOUND", "Không tìm thấy câu hỏi.")
                item.update(fields)
                item["revision"] += 1
            else:
                require(len(items) < MAX_ITEMS_PER_SET, 422, "TOO_MANY_ITEMS", f"Mỗi bộ có tối đa {MAX_ITEMS_PER_SET} câu.")
                identifier = generate_uuid7()
                item = {"id": identifier, "set_id": target, "offering_id": offering["id"], "ordinal": 1 + max((i["ordinal"] for i in items), default=0), "revision": 1, **fields}
                state.setdefault("practice_items", {})[identifier] = item
            row["revision"] += 1
            return self.practice_item_for_staff(item) | {"set_revision": row["revision"]}

        require(action == "practice-set-publish")
        require(self.feedback_public_source(state, session, row["version_id"]), 409, "SOURCE_UNAVAILABLE", "Tài liệu của bộ câu hỏi không còn khả dụng.")
        items = self.practice_items_of(state, target)
        require(bool(items), 422, "EMPTY_SET", "Bộ câu hỏi chưa có câu nào.")
        pages = payload.get("_practice_pages")
        require(isinstance(pages, dict), 409, "PAGES_NOT_CHECKED", "Chưa kiểm được trích dẫn với tài liệu.")
        problems = []
        for item in items:
            for index, check in verify_item_citations(item["citations"], {int(k): v for k, v in pages.items()}):
                problems.append({"item_id": item["id"], "citation": index, "reason": check.reason})
        if problems:
            raise LearningError(422, "CITATIONS_NOT_ON_PAGE", f"Có {len(problems)} trích dẫn không nằm đúng trên trang đã chọn.")
        row["status"], row["published_at"] = "PUBLISHED", _stamp(now)
        row["revision"] += 1
        return self.practice_set_view(row)

    async def practice_pages(self, actor, set_id) -> dict[int, str]:
        """Text of every page cited by the set's questions, read from the stored file (the part of publication that needs storage I/O)."""
        async with self.repository.transaction() as state:
            row, _, _, _ = self.practice_set_access(state, actor, set_id, manage=True)
            version = state["versions"][row["version_id"]]
            storage_key = version["storage_key"]
            wanted = sorted({c["page_no"] for i in self.practice_items_of(state, set_id) for c in i["citations"]})
        pages = {}
        for page_no in wanted:
            pages[page_no] = await self.blobs.extract_page(storage_key, page_no)
        return pages


__all__: list[Any] = ["LearningPractice", "PRACTICE_READS", "PRACTICE_WRITES"]
