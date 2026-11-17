"""Private idea cards with immutable citations and explicitly shared snapshots."""
import copy
import unicodedata
from datetime import UTC, datetime

from campus247.domain.learning import LearningError, require
from campus247.domain.shared.values import generate_uuid7

IDEA_READS = {"idea_topics", "idea_cards", "idea_card", "idea_recipients", "idea_shares", "shared_ideas", "shared_idea"}
IDEA_WRITES = {
    "idea-topic-create", "idea-topic-update", "idea-card-create", "idea-card-update", "idea-share-create", "idea-share-withdraw",
}
IDEA_FIELDS = ("problem", "idea", "verification", "source_description")


def idea_timestamp():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def normalized_quote(value):
    return " ".join(unicodedata.normalize("NFC", value).split())


class LearningIdeaCards:
    @staticmethod
    def idea_owned(state, collection, identifier, actor):
        row = state.get(collection, {}).get(identifier)
        require(row is not None and row["owner_id"] == actor.subject_id)
        return row

    def idea_public_version(self, state, offering_id, version_id):
        version = state["versions"].get(version_id)
        if version is None or version["processing_state"] != "READY" or version["publication_state"] != "PUBLISHED":
            return None
        material = state["materials"].get(version["material_id"])
        if material is None or material["offering_id"] != offering_id or material["visibility"] != "VISIBLE":
            return None
        return version, material

    def idea_source_view(self, state, source):
        data = self.idea_public_version(state, source["offering_id"], source["version_id"])
        if data is None:
            return None
        version, material = data
        if (version.get("rendition_id") or f'legacy:{version["id"]}') != source["source_key"]:
            return None
        return {key: copy.deepcopy(source[key]) for key in ("version_id", "page_no", "kind", "quote", "rects")} | {
            "title": material["title"], "version_no": version["version_no"], "rendition_id": version.get("rendition_id"),
            "offering_id": material["offering_id"],
        }

    async def verify_idea_anchor(self, actor, source):
        """Read an exact immutable rendition outside the write lock."""
        require(bool(self.idea_card_offerings) and actor.has_role("STUDENT"))
        data = await self.query(actor, "content", source["version_id"])
        require(data["offering_id"] in self.idea_card_offerings and data["publication_state"] == "PUBLISHED")
        self.feedback_page(data, source["page_no"])
        kind = source["kind"]
        quote, rects = source.get("quote"), source.get("rects", [])
        if kind == "REGION":
            require(bool(rects) and all(
                rect["width"] > 0 and rect["height"] > 0
                and rect["x"] + rect["width"] <= 1.000000001
                and rect["y"] + rect["height"] <= 1.000000001
                for rect in rects
            ), 422, "INVALID_IDEA_REGION", "Vùng dẫn nguồn phải nằm trong trang.")
        if kind == "TEXT":
            require(bool(quote and normalized_quote(quote)), 422, "INVALID_IDEA_QUOTE", "Chọn đoạn chữ cần dẫn.")
        await self.blobs.verify(data["storage_key"], data["sha256"], data["byte_size"])
        if kind == "TEXT":
            page_text = await self.blobs.extract_page(data["storage_key"], source["page_no"])
            canonical = normalized_quote(page_text)
            candidate = normalized_quote(quote)
            offset = canonical.find(candidate)
            require(offset >= 0, 422, "IDEA_QUOTE_UNVERIFIED", "Không đối chiếu được đoạn chữ. Bạn có thể dẫn cả trang hoặc vùng.")
            quote = canonical[offset:offset + len(candidate)]
        return {
            "offering_id": data["offering_id"], "version_id": data["id"], "page_no": source["page_no"],
            "source_key": data.get("rendition_id") or f'legacy:{data["id"]}', "kind": kind,
            "quote": quote if kind == "TEXT" else None, "rects": copy.deepcopy(rects) if kind == "REGION" else [],
            "sha256": data["sha256"],
        }

    def bind_idea_anchor(self, state, actor, source):
        offering, member = self.access(state, actor, source["offering_id"])
        require(offering["id"] in self.idea_card_offerings and member["role"] == "STUDENT")
        require(self.idea_source_view(state, source) is not None)
        version = state["versions"][source["version_id"]]
        self.feedback_page(version, source["page_no"])
        blob = state["blobs"].get(version["view_blob_id"]) if version.get("view_blob_id") else version
        require(blob is not None and blob["sha256"] == source["sha256"], 409, "IDEA_SOURCE_CHANGED", "Bản xem đã thay đổi.")

    @staticmethod
    def idea_topic_view(topic):
        return {key: topic[key] for key in ("id", "title", "revision", "status")}

    def idea_card_view(self, state, actor, row):
        source = row["source"]
        try:
            self.access(state, actor, source["offering_id"])
            public = self.idea_source_view(state, source)
        except LearningError as error:
            if error.status == 401:
                raise
            public = None
        if source["offering_id"] not in self.idea_card_offerings:
            public = None
        return {key: row[key] for key in ("id", "topic_id", "revision", "status", *IDEA_FIELDS)} | {
            "source": public, "source_available": public is not None,
        }

    @staticmethod
    def idea_member(state, offering, subject):
        return next((member for member in state["members"].values()
                     if member["offering_id"] == offering and member["actor_subject_id"] == subject and member["status"] == "ACTIVE"), None)

    @staticmethod
    def idea_member_guard(member):
        return [member["id"], member["revision"], member["role"]]

    @staticmethod
    def idea_source_guard(version, material):
        return [version.get("idea_source_epoch", 0), material.get("idea_visibility_epoch", 0)]

    @staticmethod
    def idea_directory_matches(directory, member):
        account = directory.get(member["actor_subject_id"])
        role = "STUDENT" if member["role"] == "STUDENT" else "LECTURER"
        return account is not None and role in account["roles"] and account.get("active", True)

    def idea_recipient_rows(self, state, actor, card):
        source = card["source"]
        offering, member = self.access(state, actor, source["offering_id"])
        require(offering["id"] in self.idea_card_offerings and member["role"] == "STUDENT" and card["status"] == "ACTIVE")
        require(self.idea_source_view(state, source) is not None)
        directory = {item["subject_id"]: item for item in self.directory_items()}
        require(self.idea_directory_matches(directory, member))
        return {
            candidate["actor_subject_id"]: candidate for candidate in state["members"].values()
            if candidate["offering_id"] == offering["id"] and candidate["status"] == "ACTIVE"
            and candidate["actor_subject_id"] != actor.subject_id and self.idea_directory_matches(directory, candidate)
        }

    def idea_share_binding(self, state, actor, card, payload):
        require(card["revision"] == payload["revision"], 409, "REVISION_CONFLICT", "Phiếu ý tưởng đã thay đổi.")
        eligible = self.idea_recipient_rows(state, actor, card)
        recipients = payload["recipient_ids"]
        require(len(recipients) == len(set(recipients)) and all(subject in eligible for subject in recipients),
                422, "IDEA_RECIPIENT_UNAVAILABLE", "Chọn người còn quyền đọc học liệu trong lớp nguồn.")
        source = card["source"]
        version, material = self.idea_public_version(state, source["offering_id"], source["version_id"])
        owner = self.idea_member(state, source["offering_id"], actor.subject_id)
        return {
            "owner_guard": self.idea_member_guard(owner), "source_guard": self.idea_source_guard(version, material),
            "recipients": {subject: self.idea_member_guard(eligible[subject]) for subject in sorted(recipients)},
        }, eligible

    def preview_idea_share(self, state, actor, card_id, payload):
        card = self.idea_owned(state, "idea_cards", card_id, actor)
        binding, eligible = self.idea_share_binding(state, actor, card, payload)
        return binding, {
            "card": self.idea_card_view(state, actor, card),
            "recipients": [{"id": subject, "label": eligible[subject]["display_name"]} for subject in payload["recipient_ids"]],
        }

    def idea_share_available(self, state, share, grant, directory):
        source = share["source"]
        offering = source["offering_id"]
        if (share["status"] != "ACTIVE" or grant is None or grant["status"] != "ACTIVE"
                or offering not in self.idea_card_offerings or self.idea_source_view(state, source) is None):
            return False
        owner = self.idea_member(state, offering, share["owner_id"])
        recipient = self.idea_member(state, offering, grant["recipient_id"])
        if owner is None or recipient is None or not all(self.idea_directory_matches(directory, item) for item in (owner, recipient)):
            return False
        version, material = self.idea_public_version(state, offering, source["version_id"])
        return (
            self.idea_member_guard(owner) == share["owner_guard"]
            and self.idea_member_guard(recipient) == grant["recipient_guard"]
            and self.idea_source_guard(version, material) == share["source_guard"]
        )

    def shared_idea_view(self, state, share):
        return {"id": share["id"], "card_revision": share["card_revision"], "shared_at": share["shared_at"],
                "source": self.idea_source_view(state, share["source"])} | share["snapshot"]

    def idea_share_owner_view(self, state, share, directory):
        active = False
        for grant in state.get("idea_grants", {}).values():
            if grant["share_id"] == share["id"]:
                active = self.check_idea_grant(state, share, grant, directory) or active
        return {key: share[key] for key in ("id", "card_id", "card_revision", "shared_at", "revision")} | {
            "status": "WITHDRAWN" if share["status"] == "WITHDRAWN" else "ACTIVE" if active else "SUSPENDED",
        }

    def read_ideas(self, state, actor, kind, target):
        if kind == "idea_topics":
            return [self.idea_topic_view(row) for row in state.get("idea_topics", {}).values() if row["owner_id"] == actor.subject_id]
        if kind == "idea_cards":
            return [self.idea_card_view(state, actor, row) for row in state.get("idea_cards", {}).values() if row["owner_id"] == actor.subject_id]
        if kind in {"idea_card", "idea_recipients"}:
            row = self.idea_owned(state, "idea_cards", target, actor)
            if kind == "idea_card":
                return self.idea_card_view(state, actor, row)
            return [{"id": subject, "label": item["display_name"]} for subject, item in self.idea_recipient_rows(state, actor, row).items()]
        directory = {item["subject_id"]: item for item in self.directory_items()}
        shares = state.get("idea_shares", {})
        grants = state.get("idea_grants", {})
        if kind == "idea_shares":
            return [self.idea_share_owner_view(state, row, directory) for row in shares.values() if row["owner_id"] == actor.subject_id]
        if kind == "shared_ideas":
            return [self.shared_idea_view(state, row) for row in shares.values()
                    if self.check_idea_grant(state, row, grants.get(f'{row["id"]}:{actor.subject_id}'), directory, actor=actor)]
        row = shares.get(target)
        if row is not None and self.check_idea_grant(state, row, grants.get(f"{target}:{actor.subject_id}"), directory, actor=actor):
            return self.shared_idea_view(state, row)
        return None

    def check_idea_grant(self, state, share, grant, directory, *, actor=None):
        if (grant is None or grant["status"] != "ACTIVE" or share["status"] != "ACTIVE"
                or share["source"]["offering_id"] not in self.idea_card_offerings):
            return False
        available = self.idea_share_available(state, share, grant, directory)
        if available and actor is not None:
            try:
                self.access(state, actor, share["source"]["offering_id"])
            except LearningError as error:
                if error.status == 401:
                    raise
                available = False
        if not available:
            grant["status"] = "SUSPENDED"
        return available

    @staticmethod
    def advance_idea_source_guard(state, action, target, payload):
        if action == "retract":
            version = state["versions"][target]
            version["idea_source_epoch"] = version.get("idea_source_epoch", 0) + 1
        if action == "material-update" and payload.get("visibility") == "HIDDEN":
            material = state["materials"][target]
            material["idea_visibility_epoch"] = material.get("idea_visibility_epoch", 0) + 1

    def authorize_idea_action(self, state, actor, action, target):
        if action in {"idea-topic-create", "idea-card-create"}:
            require(bool(self.idea_card_offerings) and actor.has_role("STUDENT"))
            return
        collection = {
            "idea-topic-update": "idea_topics", "idea-card-update": "idea_cards", "idea-share-create": "idea_cards",
            "idea-share-withdraw": "idea_shares",
        }[action]
        self.idea_owned(state, collection, target, actor)

    def idea_validate_topic(self, state, actor, identifier):
        if identifier is not None:
            row = self.idea_owned(state, "idea_topics", identifier, actor)
            require(row["status"] == "ACTIVE", 409, "IDEA_TOPIC_ARCHIVED", "Đề tài đã lưu trữ.")

    def command_idea(self, state, actor, action, target, payload, supplied):
        if action in {"idea-topic-create", "idea-topic-update"}:
            if action == "idea-topic-create":
                identifier = generate_uuid7()
                row = {"id": identifier, "owner_id": actor.subject_id, "title": payload["title"].strip(), "status": "ACTIVE", "revision": 1}
                state.setdefault("idea_topics", {})[identifier] = row
            else:
                row = self.idea_owned(state, "idea_topics", target, actor)
                require(row["revision"] == payload["revision"], 409, "REVISION_CONFLICT", "Đề tài đã thay đổi.")
                row.update(title=payload["title"].strip(), status=payload["status"], revision=row["revision"] + 1)
            return self.idea_topic_view(row)
        if action in {"idea-card-create", "idea-card-update"}:
            values = {key: payload.get(key, "").strip() for key in IDEA_FIELDS} | {"topic_id": payload.get("topic_id")}
            if action == "idea-card-create":
                self.idea_validate_topic(state, actor, values["topic_id"])
                source = payload["_idea_source"]
                self.bind_idea_anchor(state, actor, source)
                identifier = generate_uuid7()
                row = {"id": identifier, "owner_id": actor.subject_id, "source": source, "status": "ACTIVE", "revision": 1}
                state.setdefault("idea_cards", {})[identifier] = row
            else:
                row = self.idea_owned(state, "idea_cards", target, actor)
                require(row["revision"] == payload["revision"], 409, "REVISION_CONFLICT", "Phiếu ý tưởng đã thay đổi.")
                if row["topic_id"] != values["topic_id"]:
                    self.idea_validate_topic(state, actor, values["topic_id"])
                row.update(status=payload["status"], revision=row["revision"] + 1)
            row.update(values)
            row.setdefault("history", []).append(values | {"status": row["status"], "revision": row["revision"], "at": idea_timestamp()})
            return self.idea_card_view(state, actor, row)
        if action == "idea-share-withdraw":
            row = self.idea_owned(state, "idea_shares", target, actor)
            require(row["revision"] == payload["revision"], 409, "REVISION_CONFLICT", "Chia sẻ đã thay đổi.")
            if row["status"] != "WITHDRAWN":
                row.update(status="WITHDRAWN", revision=row["revision"] + 1, withdrawn_at=idea_timestamp())
            return {key: row[key] for key in ("id", "card_id", "status", "revision")}
        card = self.idea_owned(state, "idea_cards", target, actor)
        binding, _ = self.idea_share_binding(state, actor, card, payload)
        self.verify_preview(state, actor, action, target, payload | {"_idea_guard": binding}, supplied)
        identifier = generate_uuid7()
        state.setdefault("idea_shares", {})[identifier] = {
            "id": identifier, "card_id": target, "owner_id": actor.subject_id, "card_revision": card["revision"],
            "owner_guard": binding["owner_guard"], "source_guard": binding["source_guard"],
            "source": copy.deepcopy(card["source"]), "snapshot": {key: card[key] for key in IDEA_FIELDS},
            "status": "ACTIVE", "revision": 1, "shared_at": idea_timestamp(),
        }
        grants = state.setdefault("idea_grants", {})
        for subject, guard in binding["recipients"].items():
            grants[f"{identifier}:{subject}"] = {"share_id": identifier, "recipient_id": subject,
                                                  "recipient_guard": guard, "status": "ACTIVE"}
        return {"id": identifier, "card_id": target, "status": "ACTIVE", "revision": 1}
