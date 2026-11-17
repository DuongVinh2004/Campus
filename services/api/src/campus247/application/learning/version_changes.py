"""Review and publish notes between immutable versions of the same material."""
from campus247.domain.learning import require
from campus247.ports.learning_rendition import PDF_MEDIA_TYPE


class LearningVersionChanges:
    def version_change_access(self, state, actor, target, *, write=False):
        version, material, offering, member = self.version(state, actor, target)
        require(offering["id"] in self.version_change_offerings)
        require(version["processing_state"] == "READY")
        if write:
            self.access(state, actor, offering["id"], write=True)
        return version, material, member

    @staticmethod
    def change_head(state, target):
        return max(
            (row for row in state.get("version_change_revisions", {}).values() if row["target_version_id"] == target),
            key=lambda row: row["revision"], default=None,
        )

    @staticmethod
    def change_base(state, version, material, base_id):
        base = state["versions"].get(base_id)
        if (base is not None and base["material_id"] == material["id"] and base["version_no"] < version["version_no"]
                and base["processing_state"] == "READY" and base["publication_state"] == "PUBLISHED"):
            return base
        return None

    @staticmethod
    def change_projection(row, *, base_visible):
        result = {key: row[key] for key in (
            "target_version_id", "target_version_no", "target_media_type", "revision", "mode", "target_guidance",
        )}
        result["base_available"] = base_visible
        if base_visible:
            return result | {key: row[key] for key in ("base_version_id", "base_version_no", "base_media_type", "reason", "items")}
        return result | {
            "mode": "UNSPECIFIED",
            "items": [{"new_page": item["new_page"], "guidance": item["guidance"]} for item in row["items"]
                      if item.get("new_page") is not None and item.get("guidance")],
        }

    def read_version_changes(self, state, actor, target):
        version, material, member = self.version_change_access(state, actor, target)
        manage = member["role"] == "INSTRUCTOR"
        if manage:
            row = self.change_head(state, target)
        else:
            row = state.get("version_change_revisions", {}).get(f'{target}:{version.get("change_set_revision")}')
        base = row and self.change_base(state, version, material, row["base_version_id"])
        return {"change_set": self.change_projection(row, base_visible=base is not None) if row else None}

    def prepare_version_changes(self, state, actor, target, payload):
        version, material, _ = self.version_change_access(state, actor, target, write=True)
        require(version["publication_state"] in {"DRAFT", "SCHEDULED", "PUBLISHED"},
                409, "INVALID_STATE", "Phiên bản không thể sửa mô tả thay đổi.")
        head = self.change_head(state, target)
        revision = head["revision"] if head else 0
        require(payload["revision"] == revision, 409, "REVISION_CONFLICT", "Mô tả thay đổi đã có revision mới.")
        base = self.change_base(state, version, material, payload["base_version_id"])
        require(base is not None, 422, "INVALID_CHANGE_BASE", "Chọn bản trước đã công bố của cùng học liệu.")
        mode, items = payload["mode"], payload["items"]
        require(bool(items) == (mode == "PAGE_MAP"), 422, "INVALID_CHANGE_ITEMS", "Chỉ chế độ đánh dấu trang mới nhận cặp trang.")
        for item in items:
            old, new = item.get("old_page"), item.get("new_page")
            kind = item["kind"]
            require((old is not None) == (kind != "ADDED") and (new is not None) == (kind != "REMOVED"),
                    422, "INVALID_CHANGE_PAGE", "Cặp trang không phù hợp loại thay đổi.")
            if old is not None:
                self.feedback_page(base, old)
            if new is not None:
                self.feedback_page(version, new)
            require(not item.get("guidance") or new is not None, 422, "INVALID_CHANGE_PAGE", "Chỉ dẫn độc lập phải gắn với trang mới.")
        row = dict(payload) | {
            "material_id": material["id"], "target_version_id": target, "revision": revision + 1,
            "base_source_key": base.get("rendition_id") or f"legacy:{base['id']}",
            "target_source_key": version.get("rendition_id") or f"legacy:{target}",
            "base_version_no": base["version_no"], "target_version_no": version["version_no"],
            "base_media_type": base.get("source_media_type", PDF_MEDIA_TYPE),
            "target_media_type": version.get("source_media_type", PDF_MEDIA_TYPE),
        }
        return version, row

    def save_version_changes(self, state, actor, target, payload, supplied):
        version, row = self.prepare_version_changes(state, actor, target, payload)
        if version["publication_state"] == "PUBLISHED":
            self.verify_preview(state, actor, "version-change-save", target, payload, supplied)
        state.setdefault("version_change_revisions", {})[f"{target}:{row['revision']}"] = row
        if version["publication_state"] == "PUBLISHED":
            version["change_set_revision"] = row["revision"]
            version["revision"] += 1
        return self.change_projection(row, base_visible=True)

    def release_change_set(self, state, version, material, revision):
        head = self.change_head(state, version["id"])
        require(material["offering_id"] in self.version_change_offerings and head is not None
                and revision == head["revision"] and self.change_base(state, version, material, head["base_version_id"]),
                409, "CHANGE_SET_STALE", "Mô tả hoặc phiên bản trước đã thay đổi. Hãy xem trước lại.")
        return head
