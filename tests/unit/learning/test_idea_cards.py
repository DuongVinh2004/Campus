import copy
from types import SimpleNamespace

import pytest
from campus247.application.learning.idea_cards import LearningIdeaCards
from campus247.domain.learning import LearningError, require


class IdeasFixture(LearningIdeaCards):
    idea_card_offerings = frozenset({"offering"})

    def directory_items(self):
        return [{"subject_id": subject, "roles": ["STUDENT"]} for subject in ("owner", "reader")]

    def access(self, state, actor, offering_id):
        member = self.idea_member(state, offering_id, actor.subject_id)
        require(member is not None)
        return state["offerings"][offering_id], member

    def verify_preview(self, state, actor, action, target, payload, supplied):
        require(payload["_idea_guard"] == supplied["guard"], 409, "STALE_PREVIEW")


def example():
    source = {"offering_id": "offering", "version_id": "version", "source_key": "legacy:version", "page_no": 2,
              "kind": "TEXT", "quote": "trích đúng trang", "rects": []}
    card = {"id": "card", "owner_id": "owner", "topic_id": None, "source": source, "status": "ACTIVE", "revision": 1,
            "problem": "Vấn đề", "idea": "Ý tưởng trước sửa", "verification": "Cách kiểm chứng", "source_description": ""}
    state = {
        "offerings": {"offering": {"id": "offering"}},
        "versions": {"version": {"id": "version", "version_no": 1, "material_id": "material",
                                 "processing_state": "READY", "publication_state": "PUBLISHED"}},
        "materials": {"material": {"id": "material", "offering_id": "offering", "visibility": "VISIBLE", "title": "Bài giảng"}},
        "members": {subject: {"id": subject, "actor_subject_id": subject, "offering_id": "offering", "role": "STUDENT",
                              "status": "ACTIVE", "revision": 1, "display_name": subject} for subject in ("owner", "reader")},
        "idea_cards": {"card": card},
    }
    return IdeasFixture(), state, SimpleNamespace(subject_id="owner"), SimpleNamespace(subject_id="reader")


def test_idea_share_pins_content_and_does_not_revive_after_membership_change():
    service, state, owner, reader = example()
    payload = {"revision": 1, "recipient_ids": ["reader"]}
    guard, preview = service.preview_idea_share(state, owner, "card", payload)
    assert preview["card"]["source"]["quote"] == "trích đúng trang"
    share = service.command_idea(state, owner, "idea-share-create", "card", payload, {"guard": guard})
    released = copy.deepcopy(service.read_ideas(state, reader, "shared_idea", share["id"]))
    assert released["source"]["page_no"] == 2 and released["idea"] == "Ý tưởng trước sửa"
    state["idea_cards"]["card"].update(idea="Ý tưởng sau sửa", revision=2)
    assert service.read_ideas(state, reader, "shared_idea", share["id"]) == released
    state["members"]["reader"]["revision"] += 2  # Rights withdrawn and restored between reads.
    assert service.read_ideas(state, reader, "shared_idea", share["id"]) is None
    assert service.read_ideas(state, owner, "idea_shares", None)[0]["status"] == "SUSPENDED"


def test_idea_preview_binding_tracks_source_loss_and_own_card_keeps_only_own_fields():
    service, state, owner, reader = example()
    payload = {"revision": 1, "recipient_ids": ["reader"]}
    old_guard, _ = service.preview_idea_share(state, owner, "card", payload)
    state["versions"]["version"]["publication_state"] = "RETRACTED"
    service.advance_idea_source_guard(state, "retract", "version", {})
    private = service.read_ideas(state, owner, "idea_card", "card")
    assert private["source"] is None and private["idea"] == "Ý tưởng trước sửa"
    state["versions"]["version"]["publication_state"] = "PUBLISHED"
    with pytest.raises(LearningError) as stale:
        service.command_idea(state, owner, "idea-share-create", "card", payload, {"guard": old_guard})
    assert stale.value.code == "STALE_PREVIEW"
    new_guard, _ = service.preview_idea_share(state, owner, "card", payload)
    share = service.command_idea(state, owner, "idea-share-create", "card", payload, {"guard": new_guard})
    assert service.read_ideas(state, reader, "shared_idea", share["id"]) is not None
    state["materials"]["material"]["visibility"] = "HIDDEN"
    service.advance_idea_source_guard(state, "material-update", "material", {"visibility": "HIDDEN"})
    withdrawn = service.command_idea(state, owner, "idea-share-withdraw", share["id"], {"revision": 1}, {})
    assert withdrawn["status"] == "WITHDRAWN"
    assert service.read_ideas(state, reader, "shared_idea", share["id"]) is None
