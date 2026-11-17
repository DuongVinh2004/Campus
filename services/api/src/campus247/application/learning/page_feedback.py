"""Private, version-bound page feedback and its one-time collection window."""
from collections import defaultdict
from datetime import UTC, datetime

from campus247.domain.learning import require
from campus247.domain.shared.values import generate_uuid7


def feedback_clock():
    return datetime.now(UTC)


def feedback_timestamp(instant):
    return instant.isoformat(timespec="microseconds").replace("+00:00", "Z")


class LearningPageFeedback:
    def explanation_session(self, state, actor, session_id, *, manage=False):
        require(self.page_explanations_available)
        return self.feedback_session(state, actor, session_id, manage=manage)

    @staticmethod
    def explanation_view(row):
        return {key: row[key] for key in (
            "id", "session_id", "version_id", "page_no", "body", "category", "status", "revision", "published_at",
        )}

    def read_page_explanations(self, state, actor, session_id):
        session = self.explanation_session(state, actor, session_id)
        _, member = self.access(state, actor, session["offering_id"])
        return [
            self.explanation_view(row)
            for _, row in sorted(state.get("page_explanations", {}).items(), reverse=True)
            if row["session_id"] == session_id and (row["status"] == "PUBLISHED" or member["role"] == "INSTRUCTOR")
            and self.feedback_public_source(state, session, row["version_id"])
        ]

    def explanation_for_write(self, state, actor, identifier):
        row = state.get("page_explanations", {}).get(identifier)
        require(row is not None)
        session = self.explanation_session(state, actor, row["session_id"], manage=True)
        require(self.feedback_public_source(state, session, row["version_id"]))
        return row

    def command_page_explanation(self, state, actor, action, target, payload, supplied):
        if action == "page-explanation-create":
            session = self.explanation_session(state, actor, target, manage=True)
            version_id = payload["version_id"]
            require(self.feedback_public_source(state, session, version_id))
            version = state["versions"][version_id]
            self.feedback_page(version, payload["page_no"])
            identifier = generate_uuid7()
            row = {
                "id": identifier, "session_id": target, "offering_id": session["offering_id"],
                "version_id": version_id, "material_id": version["material_id"], "page_no": payload["page_no"],
                "source_key": version.get("rendition_id") or f"legacy:{version_id}", "status": "DRAFT",
                "body": payload["body"].strip(), "category": payload["category"], "revision": 1, "published_at": None,
            }
            state.setdefault("page_explanations", {})[identifier] = row
            return self.explanation_view(row)
        row = self.explanation_for_write(state, actor, target)
        require(row["revision"] == payload["revision"], 409, "REVISION_CONFLICT", "Lời giải đã thay đổi.")
        require(row["status"] == "DRAFT", 409, "INVALID_STATE", "Lời giải đã công bố được giữ nguyên.")
        if payload.get("publish"):
            self.verify_preview(state, actor, action, target, payload, supplied)
            row.update(status="PUBLISHED", published_at=feedback_timestamp(feedback_clock()))
            self.notify_page_explanation(state, row)
        else:
            row.update(body=payload["body"].strip(), category=payload["category"])
        row["revision"] += 1
        return self.explanation_view(row)

    @staticmethod
    def notify_page_explanation(state, row):
        event_id = generate_uuid7()
        event = {
            "event_type": "PAGE_EXPLANATION_PUBLISHED", "version_id": row["version_id"], "material_id": row["material_id"],
            "created_at": row["published_at"], "session_id": row["session_id"], "page_no": row["page_no"],
        }
        state["outbox"][event_id] = event | {"id": event_id, "delivered_at": row["published_at"]}
        for member in state["members"].values():
            if member["offering_id"] != row["offering_id"] or member["status"] != "ACTIVE" or member["role"] != "STUDENT":
                continue
            identifier = generate_uuid7()
            state["notifications"][identifier] = event | {
                "id": identifier, "event_id": event_id, "actor_id": member["actor_subject_id"],
                "offering_id": row["offering_id"], "read_at": None, "revision": 1, "title": "Cập nhật học liệu",
            }

    def feedback_session(self, state, actor, session_id, *, manage=False):
        session = state["sessions"].get(session_id)
        require(session is not None)
        offering, _ = self.access(state, actor, session["offering_id"], write=manage)
        require(offering["id"] in self.page_feedback_offerings)
        return session

    def feedback_source(self, state, actor, version_id, *, write=False):
        version, material, offering, member = self.version(state, actor, version_id)
        require(offering["id"] in self.page_feedback_offerings and member["role"] == "STUDENT")
        require(version["processing_state"] == "READY" and version["publication_state"] == "PUBLISHED")
        if write:
            require(offering["status"] == "ACTIVE", 409, "CLASS_ARCHIVED", "Lớp đã được lưu trữ.")
        return version, material, offering

    @staticmethod
    def feedback_page(version, page_no):
        require(type(page_no) is int and 1 <= page_no <= version["page_count"], 422, "INVALID_PAGE", "Trang không hợp lệ.")

    @staticmethod
    def own_feedback(state, actor, version_id, page_no):
        return next((
            row for row in state.get("page_feedback", {}).values()
            if row["actor_subject_id"] == actor.subject_id and row["version_id"] == version_id and row["page_no"] == page_no
        ), None)

    @staticmethod
    def feedback_view(row):
        if row is None:
            return None
        return {key: row[key] for key in ("id", "session_id", "version_id", "page_no", "category", "status", "revision")}

    @staticmethod
    def feedback_window_view(row):
        if row is None:
            return None
        return {key: row[key] for key in ("session_id", "opened_at", "closes_at", "revision")}

    @staticmethod
    def record_feedback_revision(row, instant):
        row["updated_at"] = feedback_timestamp(instant)
        row.setdefault("history", []).append({
            key: row[key] for key in ("category", "status", "revision", "updated_at")
        })

    def read_page_feedback(self, state, actor, kind, target, params):
        if kind == "feedback_window":
            self.feedback_session(state, actor, target)
            return {"window": self.feedback_window_view(state.get("feedback_windows", {}).get(target))}
        if kind == "feedback_summary":
            session = self.feedback_session(state, actor, target)
            _, member = self.access(state, actor, session["offering_id"])
            require(member["role"] == "INSTRUCTOR")
            window = state.get("feedback_windows", {}).get(target)
            if window is None:
                return {"state": "NOT_OPENED", "closes_at": None, "pages": []}
            result = {"state": "WAITING", "closes_at": window["closes_at"], "pages": []}
            if "published_summary" not in window:
                return result
            pages = window["published_summary"]
            if pages is None or any(
                not self.feedback_public_source(state, session, page["version_id"]) for page in pages
            ):
                return result | {"state": "UNAVAILABLE"}
            return result | {"state": "AVAILABLE", "pages": pages}
        version, _, _ = self.feedback_source(state, actor, target)
        page_no = params.get("page_no")
        self.feedback_page(version, page_no)
        return {"feedback": self.feedback_view(self.own_feedback(state, actor, target, page_no))}

    def authorize_page_feedback(self, state, actor, action, target):
        if action == "feedback-window-open":
            self.feedback_session(state, actor, target, manage=True)
        elif action == "page-feedback-save":
            self.feedback_source(state, actor, target, write=True)
        else:
            row = state.get("page_feedback", {}).get(target)
            require(row is not None and row["actor_subject_id"] == actor.subject_id)
            self.feedback_source(state, actor, row["version_id"])

    def command_page_feedback(self, state, actor, action, target, payload):
        instant = feedback_clock()
        if action == "feedback-window-open":
            windows = state.setdefault("feedback_windows", {})
            require(target not in windows, 409, "FEEDBACK_WINDOW_EXISTS", "Buổi đã có một cửa sổ báo vướng.")
            closes_at = datetime.fromisoformat(payload["closes_at"])
            require(closes_at > instant, 422, "FEEDBACK_INVALID_CUTOFF", "Giờ chốt phải ở trong tương lai.")
            windows[target] = {
                "session_id": target, "offering_id": state["sessions"][target]["offering_id"],
                "opened_at": feedback_timestamp(instant), "closes_at": feedback_timestamp(closes_at), "revision": 1,
            }
            self.capture_feedback_window(state, windows[target], instant)
            return self.feedback_window_view(windows[target])
        if action == "page-feedback-withdraw":
            row = state["page_feedback"][target]
            require(row["revision"] == payload["revision"], 409, "REVISION_CONFLICT", "Phản hồi đã thay đổi.")
            if row["status"] != "WITHDRAWN":
                row.update(status="WITHDRAWN", revision=row["revision"] + 1)
                self.record_feedback_revision(row, instant)
                self.capture_feedback_window(state, state["feedback_windows"][row["session_id"]], instant)
            return self.feedback_view(row)

        version, material, offering = self.feedback_source(state, actor, target, write=True)
        page_no = payload["page_no"]
        self.feedback_page(version, page_no)
        row = self.own_feedback(state, actor, target, page_no)
        require((row["revision"] if row else 0) == payload["revision"], 409, "REVISION_CONFLICT", "Phản hồi đã thay đổi.")
        session_id = payload["session_id"]
        require(row is None or row["session_id"] == session_id, 409, "FEEDBACK_SESSION_FIXED", "Phản hồi đã gắn với buổi đã chọn trước đó.")
        self.feedback_session(state, actor, session_id)
        link = state["links"].get(f"{session_id}:{material['id']}")
        require(link is not None and link["offering_id"] == offering["id"] and link.get("active", True))
        window = state.get("feedback_windows", {}).get(session_id)
        require(window is not None, 409, "FEEDBACK_WINDOW_UNAVAILABLE", "Buổi chưa mở báo vướng.")
        if row is None or row["status"] == "WITHDRAWN":
            require(instant < datetime.fromisoformat(window["closes_at"]), 409, "FEEDBACK_WINDOW_CLOSED", "Buổi đã chốt lượt báo mới.")
        if row is None:
            identifier = generate_uuid7()
            row = {
                "id": identifier, "actor_subject_id": actor.subject_id, "offering_id": offering["id"],
                "session_id": session_id, "material_id": material["id"], "version_id": target, "page_no": page_no,
                "source_key": version.get("rendition_id") or f"legacy:{target}", "revision": 0,
                "created_at": feedback_timestamp(instant),
            }
            state.setdefault("page_feedback", {})[identifier] = row
        row.update(category=payload["category"], status="ACTIVE", revision=row["revision"] + 1)
        self.record_feedback_revision(row, instant)
        self.capture_feedback_window(state, window, instant)
        return self.feedback_view(row)

    @staticmethod
    def feedback_public_source(state, session, version_id):
        version = state["versions"].get(version_id)
        if version is None or version["processing_state"] != "READY" or version["publication_state"] != "PUBLISHED":
            return False
        material = state["materials"].get(version["material_id"])
        if material is None or material["visibility"] != "VISIBLE" or material["offering_id"] != session["offering_id"]:
            return False
        link = state["links"].get(f'{session["id"]}:{material["id"]}')
        return link is not None and link.get("active", True) and link["offering_id"] == session["offering_id"]

    def capture_feedback_window(self, state, window, instant):
        # Keep the last privacy-filtered projection before the cutoff. The worker can
        # seal it later without consulting current membership, feedback or source state.
        if "published_summary" in window or instant >= datetime.fromisoformat(window["closes_at"]):
            return
        offering_id = window["offering_id"]
        session = state["sessions"][window["session_id"]]
        eligible = {
            member["actor_subject_id"]
            for member in state["members"].values()
            if member["offering_id"] == offering_id and member["role"] == "STUDENT" and member["status"] == "ACTIVE"
        }
        counts = defaultdict(set)
        if len(eligible) >= 10:
            source_visibility = {}
            for row in state.get("page_feedback", {}).values():
                actor_id, version_id = row["actor_subject_id"], row["version_id"]
                if row["session_id"] != session["id"] or row["status"] != "ACTIVE" or actor_id not in eligible:
                    continue
                if version_id not in source_visibility:
                    source_visibility[version_id] = self.feedback_public_source(state, session, version_id)
                if source_visibility[version_id]:
                    counts[(version_id, row["page_no"])].add(actor_id)
        pages = []
        for (version_id, page_no), actors in sorted(counts.items()):
            count = len(actors)
            if count >= 5:
                band = "5-9" if count < 10 else "10-19" if count < 20 else "20+"
                pages.append({"version_id": version_id, "page_no": page_no, "band": band})
        history = window.setdefault("projection_history", [])
        if not history or history[-1]["pages"] != pages:
            history.append({"captured_at": feedback_timestamp(instant), "pages": pages})

    def track_feedback_scope_change(self, state, action, target, result):
        windows = state.get("feedback_windows", {})
        if not windows:
            return
        if action in {"member-create", "member-update", "material-update", "publish", "retract", "cancel-publication"}:
            offering_id = result["offering_id"]
        elif action == "material-links":
            offering_id = state["sessions"][target]["offering_id"]
        elif action == "archive":
            offering_id = target
        else:
            return
        instant = feedback_clock()
        for window in windows.values():
            if window["offering_id"] == offering_id:
                self.capture_feedback_window(state, window, instant)

    @staticmethod
    def finalize_feedback_windows(state, instant):
        for window in state.get("feedback_windows", {}).values():
            if "published_summary" not in window and instant >= datetime.fromisoformat(window["closes_at"]):
                history = window.get("projection_history")
                window["published_summary"] = history[-1]["pages"] if history else None
