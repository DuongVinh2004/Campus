"""Version-bound private annotations, questions, reading plans and presentation."""
import copy
from datetime import UTC, datetime

from campus247.domain.learning import LearningError, require
from campus247.domain.shared.values import generate_uuid7


def stamp():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def anchor_value(anchor, page_no):
    require(isinstance(anchor, dict) and anchor.get("kind", "PAGE") in {"PAGE", "TEXT", "REGION"}, 422, "INVALID_ANCHOR", "Vị trí ghi chú không hợp lệ.")
    require(set(anchor).issubset({"kind", "x", "y", "width", "height", "text_quote", "prefix", "suffix", "rotation", "rects", "page_no"}), 422, "INVALID_ANCHOR", "Trường vị trí không hợp lệ.")
    for key in ("x", "y", "width", "height"):
        if key in anchor:
            require(isinstance(anchor[key], (int, float)) and 0 <= anchor[key] <= 1, 422, "INVALID_ANCHOR", "Tọa độ phải trong khoảng 0 đến 1.")
    text_quote = anchor.get("text_quote")
    if isinstance(text_quote, dict):
        require(set(text_quote).issubset({"exact", "prefix", "suffix"}) and isinstance(text_quote.get("exact"), str), 422, "INVALID_ANCHOR", "Trích đoạn không hợp lệ.")
        require(all(isinstance(v, str) and len(v) <= (2000 if k == "exact" else 1000) for k, v in text_quote.items()), 422, "INVALID_ANCHOR", "Trích đoạn quá dài.")
    else:
        require(text_quote is None or (isinstance(text_quote, str) and len(text_quote) <= 1000), 422, "INVALID_ANCHOR", "Trích đoạn không hợp lệ.")
    for key in ("prefix", "suffix"):
        require(isinstance(anchor.get(key, ""), str) and len(anchor.get(key, "")) <= 1000, 422, "INVALID_ANCHOR", "Trích đoạn quá dài.")
    if anchor.get("page_no"):
        require(anchor["page_no"] == page_no, 422, "INVALID_ANCHOR", "Trang ghi chú không trùng vị trí.")
    require(anchor.get("rotation", 0) in {0, 90, 180, 270}, 422, "INVALID_ANCHOR", "Góc xoay không hợp lệ.")
    rects = anchor.get("rects", [])
    require(isinstance(rects, list) and len(rects) <= 100, 422, "INVALID_ANCHOR", "Vùng chọn không hợp lệ.")
    for rect in rects:
        require(isinstance(rect, dict) and set(rect) == {"x", "y", "width", "height"}, 422, "INVALID_ANCHOR", "Vùng chọn không hợp lệ.")
        require(all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in rect.values()), 422, "INVALID_ANCHOR", "Tọa độ vùng chọn không hợp lệ.")
    return copy.deepcopy(anchor)


class LearningExtensions:
    def authorize_extension(self, s, actor, action, target):
        if action in {"annotation-create", "question-create"}:
            self.version(s, actor, target)
        elif action in {"annotation-update", "annotation-share"}:
            row = s.get("annotations", {}).get(target)
            require(row is not None and row["owner_id"] == actor.subject_id)
            self.version(s, actor, row["version_id"])
            if action == "annotation-share":
                require(row["status"] == "ACTIVE")
        elif action in {"question-update", "reply-create"}:
            row, _ = self.question_access(s, actor, target)
            if action == "question-update":
                require(row["author_id"] == actor.subject_id)
            else:
                require(row["status"] == "ACTIVE")
        elif action == "reply-endorse":
            row = s.get("replies", {}).get(target)
            require(row is not None)
            question, _ = self.question_access(s, actor, row["question_id"])
            require(question["status"] == "ACTIVE" and row["status"] == "ACTIVE")
            _, material, _, _ = self.version(s, actor, question["version_id"])
            self.access(s, actor, material["offering_id"], write=True)
        elif action in {"instruction-create", "instruction-update"}:
            if action == "instruction-update":
                row = s.get("reading_instructions", {}).get(target)
                require(row is not None)
                target = row["session_id"]
            session = s["sessions"].get(target)
            require(session is not None)
            self.access(s, actor, session["offering_id"], write=True)
        elif action == "instruction-seen":
            row = s.get("reading_instructions", {}).get(target)
            require(row is not None and row["status"] == "ACTIVE")
            self.version(s, actor, row["version_id"])
        elif action == "presentation-create":
            self.access(s, actor, target, write=True)
        elif action in {"presentation-position", "presentation-end"}:
            row = s.get("presentations", {}).get(target)
            require(row is not None and row["host_id"] == actor.subject_id)
            self.access(s, actor, row["offering_id"], write=True)
        else:
            raise LearningError(404, "RESOURCE_NOT_FOUND", "Chức năng chưa có.")

    def question_access(self, s, actor, question_id):
        question = s.get("questions", {}).get(question_id)
        require(question is not None)
        _, _, _, member = self.version(s, actor, question["version_id"])
        require(question["visibility"] == "CLASS" or question["author_id"] == actor.subject_id or member["role"] == "INSTRUCTOR")
        return question, member

    def question_dto(self, s, actor, row):
        _, member = self.question_access(s, actor, row["id"])
        can_read_private = row["author_id"] == actor.subject_id or member["role"] == "INSTRUCTOR"
        replies = [
            copy.deepcopy(reply) for reply in s["replies"].values()
            if reply["question_id"] == row["id"] and reply["status"] == "ACTIVE"
            and (can_read_private or reply.get("visibility", row["visibility"]) == "CLASS")
        ]
        return copy.deepcopy(row) | {"replies": replies}

    def annotation_share_preview(self, s, actor, target, payload):
        self.authorize_extension(s, actor, "annotation-share", target)
        note = s["annotations"][target]
        require(note["revision"] == payload["revision"], 409, "REVISION_CONFLICT", "Ghi chú đã thay đổi. Hãy xem trước lại.")
        version, material, _, _ = self.version(s, actor, note["version_id"])
        require(version["publication_state"] == "PUBLISHED" and material["visibility"] == "VISIBLE",
                409, "UNPUBLISHED_VERSION", "Cần công bố học liệu trước khi chia sẻ ghi chú.")
        return {key: copy.deepcopy(note[key]) for key in ("version_id", "page_no", "anchor", "body")} | {
            "to": "PRIVATE_TO_INSTRUCTORS",
        }

    def question_scope_preview(self, s, actor, target, payload):
        question, _ = self.question_access(s, actor, target)
        require(question["author_id"] == actor.subject_id and question["status"] == "ACTIVE")
        require(question["revision"] == payload["revision"], 409, "REVISION_CONFLICT", "Câu hỏi đã thay đổi.")
        visibility = payload.get("visibility")
        require(set(payload) == {"visibility", "revision"} and visibility in {"CLASS", "PRIVATE_TO_INSTRUCTORS"}
                and visibility != question["visibility"], 422, "INVALID_SCOPE_CHANGE", "Chỉ thay đổi phạm vi trong thao tác này.")
        if visibility == "CLASS":
            version, material, _, _ = self.version(s, actor, question["version_id"])
            require(version["publication_state"] == "PUBLISHED" and material["visibility"] == "VISIBLE",
                    409, "UNPUBLISHED_VERSION", "Cần công bố học liệu trước khi chia sẻ với lớp.")
        return {
            "from": question["visibility"], "to": visibility, "body": question["body"],
            "page_no": question["page_no"], "version_id": question["version_id"],
            "anchor": copy.deepcopy(question["anchor"]),
        }

    def notification_access(self, s, actor, row):
        require(row["actor_id"] == actor.subject_id)
        self.version(s, actor, row["version_id"])
        if row.get("event_type") == "PAGE_EXPLANATION_PUBLISHED":
            session = self.explanation_session(s, actor, row["session_id"])
            require(self.feedback_public_source(s, session, row["version_id"]))
        if row.get("event_type") == "EXIT_TICKET_UPDATED":
            self.exit_notice_access(s, actor, row)
        if row.get("question_id"):
            question, member = self.question_access(s, actor, row["question_id"])
            require(question["version_id"] == row["version_id"] and question["status"] == "ACTIVE")
            require(row["visibility"] == "CLASS" or question["author_id"] == actor.subject_id or member["role"] == "INSTRUCTOR")

    def notify_question(self, s, actor, question, event_type, *, recipient=None, visibility=None):
        version, material, _, _ = self.version(s, actor, question["version_id"])
        visibility = visibility or question["visibility"]
        event_id, created = generate_uuid7(), stamp()
        event = {
            "id": event_id, "event_type": event_type, "version_id": version["id"], "material_id": material["id"],
            "question_id": question["id"], "visibility": visibility, "page_no": question["page_no"],
            "created_at": created, "delivered_at": created,
        }
        s["outbox"][event_id] = event
        session_id = next((r["session_id"] for r in s["links"].values()
                           if r["material_id"] == material["id"] and r.get("active", True)), None)
        for member in s["members"].values():
            subject = member["actor_subject_id"]
            if (member["offering_id"] != material["offering_id"] or member["status"] != "ACTIVE"
                    or subject == actor.subject_id or (recipient is not None and subject != recipient)):
                continue
            if member["role"] != "INSTRUCTOR":
                if version["publication_state"] != "PUBLISHED" or material["visibility"] != "VISIBLE":
                    continue
                if subject != question["author_id"] and "PRIVATE_TO_INSTRUCTORS" in {visibility, question["visibility"]}:
                    continue
            key = generate_uuid7()
            s["notifications"][key] = {k: v for k, v in event.items() if k not in {"id", "delivered_at"}} | {
                "id": key, "event_id": event_id, "actor_id": subject, "offering_id": material["offering_id"],
                "session_id": session_id, "title": material["title"], "read_at": None, "revision": 1,
            }

    def query_extension(self, s, actor, kind, target, params):
        if kind == "annotations":
            result = []
            for row in s.get("annotations", {}).values():
                if row["owner_id"] != actor.subject_id or row["status"] != "ACTIVE" or (params.get("version_id") and row["version_id"] != params["version_id"]):
                    continue
                try:
                    self.version(s, actor, row["version_id"])
                except LearningError:
                    continue
                result.append(copy.deepcopy(row))
            return result
        if kind == "questions":
            self.version(s, actor, target)
            result = []
            for row in s.get("questions", {}).values():
                if row["version_id"] == target and row["status"] == "ACTIVE":
                    try:
                        result.append(self.question_dto(s, actor, row))
                    except LearningError:
                        pass
            return result
        if kind == "reading-instructions":
            session = s["sessions"].get(target)
            require(session is not None)
            _, member = self.access(s, actor, session["offering_id"])
            result = []
            for row in s.get("reading_instructions", {}).values():
                if row["session_id"] == target and row["status"] == "ACTIVE":
                    try:
                        self.version(s, actor, row["version_id"])
                        result.append(self.instruction_dto(actor, row, show_history=member["role"] == "INSTRUCTOR"))
                    except LearningError:
                        pass
            return result
        if kind in {"presentation", "presentations"}:
            if kind == "presentations":
                self.access(s, actor, target)
                result = []
                for row in s.get("presentations", {}).values():
                    if row["offering_id"] == target and row["status"] == "ACTIVE":
                        try:
                            self.version(s, actor, row["version_id"])
                            result.append(copy.deepcopy(row))
                        except LearningError:
                            pass
                return result
            row = s.get("presentations", {}).get(target)
            require(row is not None)
            self.version(s, actor, row["version_id"])
            return copy.deepcopy(row)
        raise LearningError(404, "RESOURCE_NOT_FOUND", "Không tìm thấy chức năng học liệu.")

    @staticmethod
    def instruction_dto(actor, row, *, show_history=False):
        result = {key: copy.deepcopy(value) for key, value in row.items() if key not in {"seen", "history"}}
        mark = row.get("seen", {}).get(actor.subject_id, {})
        result["seen_at"] = mark.get("at") if mark.get("revision") == row["revision"] else None
        if show_history:
            result["history"] = copy.deepcopy(row.get("history", []))
        return result

    def command_extension(self, s, actor, action, target, p, supplied):
        base = {"id": generate_uuid7(), "revision": 1, "created_at": stamp(), "status": "ACTIVE"}
        if action == "annotation-share":
            preview = self.annotation_share_preview(s, actor, target, p)
            note = s["annotations"][target]
            return self.command_extension(s, actor, "question-create", note["version_id"], {
                **{key: preview[key] for key in ("page_no", "anchor", "body")},
                "rendition_id": note.get("rendition_id"), "visibility": preview["to"],
            }, {})
        if action in {"annotation-create", "question-create"}:
            version_id = p.get("version_id") or target
            version, _, _, _ = self.version(s, actor, version_id)
            rendition_id = version.get('rendition_id')
            require(p.get('rendition_id') in {None, rendition_id}, 409, 'RENDITION_MISMATCH', 'Vị trí ghi chú thuộc bản xem khác.')
            if version.get('source_media_type') == 'application/vnd.openxmlformats-officedocument.presentationml.presentation':
                require(bool(rendition_id) and p.get('rendition_id') == rendition_id, 409, 'RENDITION_REQUIRED', 'Cần neo trao đổi vào đúng bản PDF chuyển đổi.')
            require(version["processing_state"] == "READY" and 1 <= p["page_no"] <= version["page_count"], 422, "INVALID_PAGE", "Trang chưa sẵn sàng hoặc không tồn tại.")
            anchor = anchor_value(p.get("anchor", {"kind": "PAGE"}), p["page_no"])
            require(isinstance(p["body"], str) and 0 < len(p["body"].strip()) <= 5000, 422, "INVALID_BODY", "Nội dung phải có từ 1 đến 5000 ký tự.")
            row = base | {"version_id": version_id, "page_no": p["page_no"], "anchor": anchor, "body": p["body"]}
            if rendition_id:
                row['rendition_id'] = rendition_id
            if action == "annotation-create":
                row["owner_id"] = actor.subject_id
                s.setdefault("annotations", {})[row["id"]] = row
                return row
            row.update(author_id=actor.subject_id, author_name=actor.display_name, visibility=p.get("visibility", "PRIVATE_TO_INSTRUCTORS"))
            require(row["visibility"] in {"CLASS", "PRIVATE_TO_INSTRUCTORS"}, 422, "INVALID_VISIBILITY", "Phạm vi câu hỏi không hợp lệ.")
            s.setdefault("questions", {})[row["id"]] = row
            self.notify_question(s, actor, row, "QUESTION_CREATED")
            return self.question_dto(s, actor, row)
        if action == "annotation-update":
            row = s.get("annotations", {}).get(target)
            require(row is not None and row["owner_id"] == actor.subject_id)
            self.version(s, actor, row["version_id"])
            require(row["revision"] == p["revision"], 409, "REVISION_CONFLICT", "Ghi chú đã thay đổi.")
            row.update({k: v for k, v in p.items() if k in {"body", "status"}}, revision=row["revision"] + 1)
            return row
        if action in {"question-update", "reply-create"}:
            question, _ = self.question_access(s, actor, target)
            if action == "reply-create":
                require(question["revision"] == p["question_revision"], 409, "REVISION_CONFLICT", "Phạm vi hoặc nội dung câu hỏi đã thay đổi. Tải lại trước khi trả lời.")
                row = base | {"question_id": target, "body": p["body"], "author_id": actor.subject_id, "author_name": actor.display_name, "visibility": question["visibility"], "endorsed": False}
                s.setdefault("replies", {})[row["id"]] = row
                self.notify_question(s, actor, question, "QUESTION_REPLIED", recipient=question["author_id"])
                return row
            require(question["author_id"] == actor.subject_id, 403, "FORBIDDEN", "Chỉ người hỏi được sửa câu hỏi.")
            require(question["revision"] == p["revision"], 409, "REVISION_CONFLICT", "Câu hỏi đã thay đổi.")
            if "visibility" in p and p["visibility"] != question["visibility"]:
                self.question_scope_preview(s, actor, target, p)
                self.verify_preview(s, actor, action, target, p, supplied)
                for reply in s["replies"].values():
                    if reply["question_id"] == target:
                        reply.setdefault("visibility", question["visibility"])
                question.update(visibility=p["visibility"], revision=question["revision"] + 1)
                self.notify_question(s, actor, question, "QUESTION_SCOPE_CHANGED")
                return self.question_dto(s, actor, question)
            question.update({k: v for k, v in p.items() if k in {"body", "status"}}, revision=question["revision"] + 1)
            return self.question_dto(s, actor, question)
        if action == "reply-endorse":
            row = s.get("replies", {}).get(target)
            require(row is not None)
            question, _member = self.question_access(s, actor, row["question_id"])
            _, material, _, _ = self.version(s, actor, question["version_id"])
            self.access(s, actor, material["offering_id"], write=True)
            if row["endorsed"]:
                return row
            row.update(endorsed=True, endorsed_by=actor.subject_id, revision=row["revision"] + 1)
            self.notify_question(s, actor, question, "REPLY_ENDORSED", recipient=row["author_id"],
                                 visibility=row.get("visibility", question["visibility"]))
            return row
        if action == "instruction-seen":
            row = s["reading_instructions"][target]
            require(row["revision"] == p["revision"], 409, "REVISION_CONFLICT", "Chỉ dẫn đã thay đổi. Hãy mở lại trước khi đánh dấu.")
            seen = row.setdefault("seen", {})
            mark = seen.get(actor.subject_id, {})
            if mark.get("revision") != row["revision"]:
                seen[actor.subject_id] = {"revision": row["revision"], "at": stamp()}
            return self.instruction_dto(actor, row)
        if action in {"instruction-create", "instruction-update"}:
            if action == "instruction-create":
                session = s["sessions"].get(target)
                require(session is not None)
                self.access(s, actor, session["offering_id"], write=True)
                row = base | p | {"session_id": target}
            else:
                previous = s["reading_instructions"][target]
                session = s["sessions"][previous["session_id"]]
                self.access(s, actor, session["offering_id"], write=True)
                require(previous["revision"] == p["revision"], 409, "REVISION_CONFLICT", "Chỉ dẫn đã thay đổi.")
                row = copy.deepcopy(previous) | p | {"revision": previous["revision"] + 1}
                saved = {key: copy.deepcopy(previous[key]) for key in
                         ("revision", "version_id", "page_ranges", "purpose", "timing", "questions", "status") if key in previous}
                saved["replaced_at"] = stamp()
                row.setdefault("history", []).append(saved)
            version, material, _, _ = self.version(s, actor, row["version_id"])
            require(material["offering_id"] == session["offering_id"], 422, "CROSS_CLASS_LINK", "Tài liệu không thuộc lớp.")
            require(version["publication_state"] == "PUBLISHED", 409, "UNPUBLISHED_VERSION", "Chỉ giao đọc tài liệu đã công bố.")
            require(0 < len(row["page_ranges"]) <= 50, 422, "INVALID_PAGES", "Phạm vi trang không hợp lệ.")
            for interval in row["page_ranges"]:
                require(set(interval) == {"start", "end"} and isinstance(interval["start"], int) and isinstance(interval["end"], int) and 1 <= interval["start"] <= interval["end"] <= version["page_count"], 422, "INVALID_PAGES", "Phạm vi trang không hợp lệ.")
            row["offering_id"] = session["offering_id"]
            s.setdefault("reading_instructions", {})[row["id"]] = row
            return self.instruction_dto(actor, row, show_history=True)
        if action == "presentation-create":
            self.access(s, actor, target, write=True)
            version, material, _, _ = self.version(s, actor, p["version_id"])
            require(material["offering_id"] == target and version["publication_state"] == "PUBLISHED", 422, "INVALID_PRESENTATION", "Phiên bản chưa được công bố trong lớp.")
            require(not any(r["offering_id"] == target and r["status"] == "ACTIVE" for r in s.get("presentations", {}).values()), 409, "PRESENTATION_ACTIVE", "Lớp đã có phiên trình bày đang hoạt động.")
            row = base | {"offering_id": target, "version_id": version["id"], "host_id": actor.subject_id, "page_no": 1, "sequence": 1}
            s.setdefault("presentations", {})[row["id"]] = row
            return row
        if action in {"presentation-position", "presentation-end"}:
            row = s.get("presentations", {}).get(target)
            require(row is not None)
            self.access(s, actor, row["offering_id"], write=True)
            require(row["host_id"] == actor.subject_id and row["status"] == "ACTIVE", 403, "FORBIDDEN", "Bạn không điều khiển phiên này.")
            version, _, _, _ = self.version(s, actor, row["version_id"])
            if action == "presentation-position":
                require(p["sequence"] == row["sequence"], 409, "REVISION_CONFLICT", "Trang trình bày đã thay đổi.")
                require(1 <= p["page_no"] <= version["page_count"], 422, "INVALID_PAGE", "Trang không hợp lệ.")
                row["page_no"] = p["page_no"]
            else:
                row["status"] = "ENDED"
            row.update(sequence=row["sequence"] + 1, revision=row["revision"] + 1, updated_at=stamp())
            return row
        raise LearningError(404, "RESOURCE_NOT_FOUND", "Chức năng chưa có.")
