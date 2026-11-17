"""Version-bound exit tickets, private submission receipts and class review."""
import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from campus247.domain.learning import LearningError, require
from campus247.domain.shared.values import generate_uuid7

EXIT_TICKET_READS = {"exit_tickets", "exit_ticket", "exit_submission", "exit_submissions", "exit_review"}
EXIT_TICKET_WRITES = {"exit-ticket-create", "exit-ticket-update", "exit-submission-save", "exit-review-save"}
EXIT_TICKET_NOTICE = "EXIT_TICKET_UPDATED"


def exit_clock():
    return datetime.now(UTC)


def utc_stamp(value):
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def class_wall_time(value, zone_id):
    local = value["local"]
    require(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", local)), 422, "INVALID_WALL_TIME",
            "Nhập ngày giờ địa phương theo phút.")
    try:
        naive = datetime.fromisoformat(local)
        zone = ZoneInfo(zone_id)
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise LearningError(422, "INVALID_CLASS_TIME", "Không xác định được giờ hoặc múi giờ của lớp.") from error
    candidates = {}
    try:
        for fold in (0, 1):
            local_time = naive.replace(tzinfo=zone, fold=fold)
            instant = local_time.astimezone(UTC)
            if instant.astimezone(zone).replace(tzinfo=None) == naive:
                candidates[int(local_time.utcoffset().total_seconds() // 60)] = instant
    except OverflowError as error:
        raise LearningError(422, "INVALID_CLASS_TIME", "Giờ lớp nằm ngoài phạm vi có thể lưu.") from error
    require(bool(candidates), 422, "NONEXISTENT_WALL_TIME", "Giờ này không tồn tại trong múi giờ của lớp.")
    selected = value.get("offset_minutes")
    if len(candidates) > 1:
        require(selected is not None, 422, "AMBIGUOUS_WALL_TIME", "Giờ bị lặp. Hãy chọn độ lệch UTC.")
    offset = selected if selected is not None else next(iter(candidates))
    require(offset in candidates, 422, "INVALID_TIME_OFFSET", "Độ lệch UTC không khớp giờ lớp.")
    return {"local": local, "offset_minutes": offset, "utc": utc_stamp(candidates[offset])}


class LearningExitTickets:
    def exit_session(self, state, actor, session_id, *, manage=False):
        session = state["sessions"].get(session_id)
        require(session is not None)
        offering, member = self.access(state, actor, session["offering_id"], write=manage)
        require(offering["id"] in self.exit_ticket_offerings)
        return session, offering, member

    def exit_ticket_access(self, state, actor, ticket_id, *, manage=False):
        row = state.get("exit_tickets", {}).get(ticket_id)
        require(row is not None)
        session, offering, member = self.exit_session(state, actor, row["session_id"], manage=manage)
        require(row["offering_id"] == offering["id"])
        if member["role"] == "STUDENT":
            require(row.get("published_question_revision") is not None)
        return row, session, offering, member

    def exit_notice_access(self, state, actor, notice):
        session, _, _ = self.exit_session(state, actor, notice["session_id"])
        require(self.feedback_public_source(state, session, notice["version_id"]))

    def require_exit_source(self, state, row, session):
        require(self.feedback_public_source(state, session, row["version_id"]))

    @staticmethod
    def exit_state(row, instant):
        if row["status"] != "PUBLISHED":
            return row["status"]
        if instant < datetime.fromisoformat(row["opens"]["utc"]):
            return "SCHEDULED"
        return "OPEN" if instant < datetime.fromisoformat(row["closes"]["utc"]) else "CLOSED"

    def exit_ticket_view(self, state, row, session, instant):
        result = {key: row[key] for key in ("id", "session_id", "revision")}
        if not self.feedback_public_source(state, session, row["version_id"]):
            return result | {"state": "SOURCE_UNAVAILABLE"}
        return result | {"state": self.exit_state(row, instant)} | {
            key: row[key] for key in ("version_id", "page_no", "question", "zone_id", "opens", "closes", "instruction")
        }

    @staticmethod
    def exit_submission_view(row, *, history=False):
        if row is None:
            return None
        result = {key: row[key] for key in ("ticket_id", "answer", "revision", "receipt_id", "submitted_at")}
        return result | {"history": row["history"]} if history else result

    @staticmethod
    def exit_review_view(row, *, staff=False):
        if row is None:
            return None
        if staff:
            return {key: row[key] for key in ("revision", "topics", "next_plan", "explanation", "published")}
        return {"published": row["published"]} if row["published"] else None

    def read_exit_tickets(self, state, actor, kind, target):
        instant = exit_clock()
        if kind == "exit_tickets":
            session, _, member = self.exit_session(state, actor, target)
            return [self.exit_ticket_view(state, row, session, instant)
                    for _, row in sorted(state.get("exit_tickets", {}).items(), reverse=True)
                    if row["session_id"] == target and (member["role"] == "INSTRUCTOR" or row.get("published_question_revision"))]
        row, session, _, member = self.exit_ticket_access(state, actor, target)
        if kind == "exit_ticket":
            return self.exit_ticket_view(state, row, session, instant)
        if kind == "exit_submission":
            require(member["role"] == "STUDENT")
            submission = state.get("exit_submissions", {}).get(f"{target}:{actor.subject_id}")
            return {"submission": self.exit_submission_view(submission, history=True)}
        self.require_exit_source(state, row, session)
        staff = member["role"] == "INSTRUCTOR"
        if kind == "exit_submissions":
            require(staff)
            return [self.exit_submission_view(submission) | {"id": submission["student_id"], "student_id": submission["student_id"]}
                    for _, submission in sorted(state.get("exit_submissions", {}).items())
                    if submission["ticket_id"] == target]
        return {"review": self.exit_review_view(state.get("exit_reviews", {}).get(target), staff=staff)}

    def exit_instruction_binding(self, state, session, version_id, reference):
        if reference is None:
            return None
        instruction = state.get("reading_instructions", {}).get(reference["id"])
        require(instruction is not None and instruction["session_id"] == session["id"], 422,
                "INVALID_INSTRUCTION", "Chọn chỉ dẫn đọc trong cùng buổi.")
        revisions = [instruction, *instruction.get("history", [])]
        selected = next((item for item in revisions if item["revision"] == reference["revision"]), None)
        require(selected is not None and selected["version_id"] == version_id and selected.get("status", "ACTIVE") == "ACTIVE",
                422, "INVALID_INSTRUCTION", "Revision chỉ dẫn phải thuộc phiên bản đã chọn.")
        return {"id": reference["id"], **{key: selected[key] for key in ("revision", "purpose", "page_ranges")}}

    def exit_draft_fields(self, state, session, offering, draft):
        version_id = draft["version_id"]
        require(self.feedback_public_source(state, session, version_id))
        version = state["versions"][version_id]
        self.feedback_page(version, draft["page_no"])
        zone = state["terms"].get(offering["term_id"], {}).get("timezone") or "Asia/Bangkok"
        opens, closes = (class_wall_time(draft[field], zone) for field in ("opens", "closes"))
        require(datetime.fromisoformat(opens["utc"]) < datetime.fromisoformat(closes["utc"]), 422,
                "INVALID_TICKET_WINDOW", "Giờ đóng phải sau giờ mở.")
        return {
            "version_id": version_id, "page_no": draft["page_no"], "material_id": version["material_id"],
            "source_key": version.get("rendition_id") or f"legacy:{version_id}", "question": draft["question"].strip(),
            "zone_id": zone, "opens": opens, "closes": closes,
            "instruction": self.exit_instruction_binding(state, session, version_id, draft.get("instruction")),
        }

    def authorize_exit_action(self, state, actor, action, target):
        if action == "exit-ticket-create":
            self.exit_session(state, actor, target, manage=True)
            return
        row, session, _, member = self.exit_ticket_access(state, actor, target, manage=action != "exit-submission-save")
        if action == "exit-submission-save":
            require(member["role"] == "STUDENT")
        if action == "exit-review-save":
            self.require_exit_source(state, row, session)

    def replay_exit_action(self, state, actor, action, target, previous):
        if action in {"exit-ticket-create", "exit-ticket-update"}:
            ticket_id = previous["id"] if action == "exit-ticket-create" else target
            row, session, _, _ = self.exit_ticket_access(state, actor, ticket_id, manage=True)
            if not self.feedback_public_source(state, session, row["version_id"]) or not self.feedback_public_source(
                state, session, previous.get("version_id")
            ):
                return {key: previous[key] for key in ("id", "session_id", "revision")} | {"state": "SOURCE_UNAVAILABLE"}
        return previous

    def exit_impact(self, state, row):
        return {
            "students": sum(member["offering_id"] == row["offering_id"] and member["status"] == "ACTIVE"
                            and member["role"] == "STUDENT" for member in state["members"].values()),
            "submissions": sum(item["ticket_id"] == row["id"] for item in state.get("exit_submissions", {}).values()),
        }

    def exit_transition(self, state, row, session, payload, instant):
        require(payload["revision"] == row["revision"], 409, "REVISION_CONFLICT", "Phiếu đã thay đổi.")
        operation = payload["operation"]
        if operation == "CANCEL":
            require(row["status"] in {"DRAFT", "PUBLISHED"}, 409, "INVALID_TICKET_STATE", "Phiếu đã hủy.")
            return {"status": "CANCELLED"}
        self.require_exit_source(state, row, session)
        if operation == "PUBLISH":
            require(row["status"] == "DRAFT" and instant < datetime.fromisoformat(row["closes"]["utc"]),
                    409, "INVALID_TICKET_STATE", "Chỉ công bố bản nháp còn hạn.")
            return {"status": "PUBLISHED", "published_question_revision": row["revision"] + 1}
        require(operation == "EXTEND" and row["status"] == "PUBLISHED", 409, "INVALID_TICKET_STATE", "Chỉ gia hạn phiếu đã công bố.")
        previous = datetime.fromisoformat(row["closes"]["utc"])
        require(instant < previous, 409, "TICKET_CLOSED", "Phiếu đã đóng, không thể mở lại.")
        closes = class_wall_time(payload["closes"], row["zone_id"])
        require(datetime.fromisoformat(closes["utc"]) > previous, 422, "INVALID_TICKET_WINDOW", "Mốc gia hạn phải muộn hơn hạn hiện tại.")
        return {"closes": closes}

    def preview_exit_action(self, state, actor, action, target, payload):
        row, session, _, _ = self.exit_ticket_access(state, actor, target, manage=True)
        instant = exit_clock()
        if action == "exit-ticket-update":
            update = self.exit_transition(state, row, session, payload, instant)
            preview = self.exit_ticket_view(state, row | update, session, instant)
            return {"exit_ticket": preview | self.exit_impact(state, row)}
        review = self.prepare_exit_review(state, row, session, payload, instant)
        require(payload["operation"] == "PUBLISH", 422, "INVALID_REVIEW_OPERATION", "Chọn công bố lời giải.")
        return {"exit_review": {"explanation": review["explanation"], "revision": review["revision"]}}

    def notify_exit_class(self, state, row, instant):
        event_id = generate_uuid7()
        event = {
            "event_type": EXIT_TICKET_NOTICE, "version_id": row["version_id"], "material_id": row["material_id"],
            "created_at": utc_stamp(instant), "session_id": row["session_id"], "page_no": row["page_no"],
            "exit_ticket_id": row["id"],
        }
        state["outbox"][event_id] = event | {"id": event_id, "delivered_at": event["created_at"]}
        for member in state["members"].values():
            if member["offering_id"] != row["offering_id"] or member["status"] != "ACTIVE" or member["role"] != "STUDENT":
                continue
            identifier = generate_uuid7()
            state["notifications"][identifier] = event | {
                "id": identifier, "event_id": event_id, "actor_id": member["actor_subject_id"],
                "offering_id": row["offering_id"], "read_at": None, "revision": 1, "title": "Cập nhật phiếu ra lớp",
            }

    def command_exit_ticket(self, state, actor, action, target, payload, supplied):
        if action == "exit-ticket-create":
            session, offering, _ = self.exit_session(state, actor, target, manage=True)
            identifier = generate_uuid7()
            instant = exit_clock()
            row = self.exit_draft_fields(state, session, offering, payload) | {
                "id": identifier, "session_id": target, "offering_id": offering["id"], "status": "DRAFT", "revision": 1,
            }
            state.setdefault("exit_tickets", {})[identifier] = row
            return self.exit_ticket_view(state, row, session, instant)

        row, session, offering, _ = self.exit_ticket_access(state, actor, target, manage=action != "exit-submission-save")
        if action == "exit-submission-save":
            return self.save_exit_submission(state, actor, row, session, offering, payload)
        instant = exit_clock()
        if action == "exit-review-save":
            return self.save_exit_review(state, actor, row, session, payload, supplied, instant)
        operation = payload["operation"]
        if operation == "EDIT_DRAFT":
            require(payload["revision"] == row["revision"], 409, "REVISION_CONFLICT", "Phiếu đã thay đổi.")
            require(row["status"] == "DRAFT", 409, "INVALID_TICKET_STATE", "Đề đã công bố được giữ nguyên.")
            fields = self.exit_draft_fields(state, session, offering, payload["draft"])
        else:
            fields = self.exit_transition(state, row, session, payload, instant)
            self.verify_preview(state, actor, action, target, payload, supplied)
        previous = {key: value for key, value in row.items() if key != "history"}
        row.setdefault("history", []).append(previous | {"replaced_at": utc_stamp(instant)})
        row.update(fields, revision=row["revision"] + 1)
        if operation != "EDIT_DRAFT" and row.get("published_question_revision") and self.feedback_public_source(state, session, row["version_id"]):
            self.notify_exit_class(state, row, instant)
        return self.exit_ticket_view(state, row, session, instant)

    def save_exit_submission(self, state, actor, row, session, offering, payload):
        self.require_exit_source(state, row, session)
        require(offering["status"] == "ACTIVE", 409, "CLASS_ARCHIVED", "Lớp đã được lưu trữ.")
        key = f'{row["id"]}:{actor.subject_id}'
        submissions = state.setdefault("exit_submissions", {})
        previous = submissions.get(key)
        revision = previous["revision"] if previous else 0
        require(payload["revision"] == revision, 409, "REVISION_CONFLICT", "Bài nộp đã thay đổi trên thiết bị khác.")
        instant = exit_clock()
        require(self.exit_state(row, instant) == "OPEN", 409, "TICKET_NOT_OPEN", "Phiếu hiện không nhận bài.")
        receipt = {
            "ticket_id": row["id"], "answer": payload["answer"].strip(), "revision": revision + 1,
            "receipt_id": generate_uuid7(), "submitted_at": utc_stamp(instant),
        }
        history = list(previous["history"]) if previous else []
        history.append(receipt.copy())
        submissions[key] = receipt | {"history": history, "student_id": actor.subject_id, "offering_id": offering["id"],
                                      "question_revision": row["published_question_revision"]}
        return self.exit_submission_view(submissions[key])

    def prepare_exit_review(self, state, row, session, payload, instant):
        self.require_exit_source(state, row, session)
        require(self.exit_state(row, instant) == "CLOSED", 409, "REVIEW_NOT_OPEN", "Chỉ rà bài sau khi phiếu đóng.")
        previous = state.get("exit_reviews", {}).get(row["id"])
        revision = previous["revision"] if previous else 0
        require(payload["revision"] == revision, 409, "REVISION_CONFLICT", "Bản rà bài đã thay đổi.")
        if payload["operation"] == "PUBLISH":
            require(previous is not None and previous["explanation"], 409, "NO_REVIEW_DRAFT", "Hãy lưu lời giải nháp trước.")
            return previous
        return {"ticket_id": row["id"], "topics": payload["topics"].strip(), "next_plan": payload["next_plan"].strip(),
                "explanation": payload["explanation"].strip(), "revision": revision,
                "published": previous["published"] if previous else None}

    def save_exit_review(self, state, actor, row, session, payload, supplied, instant):
        review = self.prepare_exit_review(state, row, session, payload, instant)
        updated = review | {"revision": review["revision"] + 1}
        if payload["operation"] == "PUBLISH":
            self.verify_preview(state, actor, "exit-review-save", row["id"], payload, supplied)
            updated["published"] = {"explanation": review["explanation"], "published_at": utc_stamp(instant)}
            self.notify_exit_class(state, row, instant)
        reviews = state.setdefault("exit_reviews", {})
        previous = reviews.get(row["id"])
        history = list(previous.get("history", [])) if previous else []
        history.append({key: value for key, value in updated.items() if key != "history"} | {"saved_at": utc_stamp(instant)})
        reviews[row["id"]] = updated | {"history": history}
        return self.exit_review_view(updated, staff=True)
