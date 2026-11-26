"""F0.1 / F0.3: registry validity, value resolution, the preview -> confirm flow and propagation between two processes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from campus247.application.features.service import FeatureService
from campus247.features import registry as reg
from campus247.infrastructure.repositories.sqlite_feature_flags import FeatureStore
from campus247.ports.campus_ops import OpsError
from campus247.ports.identity import IdentityContext, IdentityRole

NOW = datetime(2026, 11, 26, 3, 0, tzinfo=timezone.utc)


def person(role=IdentityRole.KNOWLEDGE_ADMIN, subject="01900000-0000-7000-8000-00000000000a"):
    kwargs = {"student_code": "S1"} if role == IdentityRole.STUDENT else {}
    return IdentityContext(subject_id=subject, external_subject="x", issuer="local", roles=(role,), display_name="x",
                           auth_time=NOW, expires_at=NOW + timedelta(hours=1), **kwargs)


def make(tmp_path, **kw):
    clock = kw.pop("clock", lambda: NOW)
    return FeatureService(store=FeatureStore(tmp_path / "ff.sqlite3"), clock=clock, monotonic=kw.pop("monotonic", lambda: 1e6), **kw)


def change(svc, actor, key, value, reason="Bảo trì theo kế hoạch tuần này", idem="k1", **kw):
    pv = svc.preview_change(actor, key, value=value, reason=reason, expected_version=svc.version(), **kw)
    return svc.confirm_change(actor, pv["preview_id"], pv["confirmation_token"], idem)


def test_registry_is_valid_and_new_features_default_off():
    assert reg.validate_registry() == []
    new = [k for k in reg.BY_KEY if k.split(".")[0] in {"announcements", "policy", "agent", "proactive", "input", "output"} or k in
           {"chat.evidence_receipts", "chat.evidence_ui", "learning.tutor", "learning.mastery_map"}]
    assert new and all(reg.BY_KEY[k].default is False for k in new)


def test_registry_rejects_cycle_duplicate_and_weakening_name():
    a = reg._f("x.a", "a", "core", depends_on=("x.b",))
    b = reg._f("x.b", "b", "core", depends_on=("x.a",))
    assert any("cycle" in p for p in reg.validate_registry((a, b)))
    assert any("duplicate" in p for p in reg.validate_registry((a, a)))
    assert any("weaken" in p for p in reg.validate_registry((reg._f("x.skip_verify", "v", "core"),)))
    assert any("locked" in p for p in reg.validate_registry((reg._f("x.l", "l", "core", locked=True, depends_on=("x.a",)), a)))


def test_priority_emergency_over_override_over_env_over_profile_over_default(tmp_path):
    admin = person()
    svc = make(tmp_path, profile_values={"chat.answer_cache": True}, env={"CAMPUS247_RAG_ANSWER_CACHE": "0"})
    assert svc.explain("chat.answer_cache").source == "env" and not svc.enabled("chat.answer_cache")
    change(svc, admin, "chat.answer_cache", True)
    assert svc.explain("chat.answer_cache").source == "override" and svc.enabled("chat.answer_cache")
    off = make(tmp_path, env={"CAMPUS247_FEATURES_OFF": "chat.answer_cache"})
    off._cache_at = -1e9
    assert off.explain("chat.answer_cache").reasons == ("EMERGENCY_OFF",) and not off.enabled("chat.answer_cache")
    assert make(tmp_path, env={"CAMPUS247_FEATURES_OFF": "*"}).enabled("core.auth")  # locked stays on


def test_dependency_transitive_and_explain_codes(tmp_path):
    admin = person()
    svc = make(tmp_path, env={"CAMPUS247_FEATURES_OFF": "notifications.inbox"})
    assert not svc.enabled("reminders.exam")
    assert "DEPENDENCY_OFF:notifications.inbox" in svc.explain("reminders.exam").reasons
    assert svc.explain("announcements.publish").reasons[0] == "CONFIGURED_OFF"
    wired = make(tmp_path, wired=frozenset())
    change(wired, admin, "learning.core", True, idem="w")
    assert wired.explain("learning.core").reasons == ("NOT_WIRED_RESTART_REQUIRED",)
    state = make(tmp_path, capabilities=lambda: {"chat_generation": False})
    assert state.enabled("chat.assistant")  # write-scope capability does not hide reads
    assert state.gate("/v1/conversations", "POST", None) == "chat.assistant"
    assert state.gate("/v1/conversations", "GET", None) is None


def test_variants_and_legacy_env(tmp_path):
    svc = make(tmp_path, env={"CAMPUS247_RAG_SKIP_VERBATIM_SEMANTIC": "shadow", "CAMPUS_LEARNING_AI_ENABLED": "true"}, wired=frozenset({"learning.ai_explanations", "learning.core"}))
    assert svc.value("chat.verbatim_skip") == "shadow"
    assert svc.enabled("learning.ai_explanations") and svc.enabled("learning.core")
    assert make(tmp_path, env={"CAMPUS247_RAG_SKIP_VERBATIM_SEMANTIC": "bogus"}).value("chat.verbatim_skip") == "off"


def test_expiry_audience_percent_is_stable(tmp_path):
    admin, student = person(), person(IdentityRole.STUDENT, "01900000-0000-7000-8000-00000000000b")
    now = [NOW]
    svc = make(tmp_path, clock=lambda: now[0])
    change(svc, admin, "rooms.booking", False, expires_at=(NOW + timedelta(hours=1)).isoformat())
    assert not svc.enabled("rooms.booking")
    now[0] = NOW + timedelta(hours=2)
    assert svc.enabled("rooms.booking")  # expired -> next source
    now[0] = NOW
    assert svc._percent("rooms.booking", student.subject_id) == svc._percent("rooms.booking", student.subject_id)
    assert {svc._percent("a.b", f"s{i}") for i in range(50)} <= set(range(100))


def test_audience_roles_and_subjects(tmp_path):
    admin, student = person(), person(IdentityRole.STUDENT, "01900000-0000-7000-8000-00000000000b")
    svc = make(tmp_path)
    change(svc, admin, "rooms.booking", False, audience={"roles": ["STUDENT"]})
    assert not svc.enabled("rooms.booking", student) and svc.enabled("rooms.booking", admin) and svc.enabled("rooms.booking")
    assert svc.explain("rooms.booking", admin).source != "override"


def test_change_flow_errors_and_idempotency(tmp_path):
    admin, student = person(), person(IdentityRole.STUDENT, "01900000-0000-7000-8000-00000000000b")
    svc = make(tmp_path)

    def code(fn):
        with pytest.raises(OpsError) as caught:
            fn()
        return caught.value.code

    assert code(lambda: svc.preview_change(student, "rooms.booking", value=False, reason="x" * 12, expected_version=0)) == "FORBIDDEN"
    assert code(lambda: svc.preview_change(person(IdentityRole.KNOWLEDGE_CONTRIBUTOR), "rooms.booking", value=False, reason="x" * 12, expected_version=0)) == "FORBIDDEN"
    assert code(lambda: svc.preview_change(admin, "nope.nope", value=False, reason="x" * 12, expected_version=0)) == "FEATURE_UNKNOWN"
    assert code(lambda: svc.preview_change(admin, "core.auth", value=False, reason="x" * 12, expected_version=0)) == "FEATURE_LOCKED"
    assert code(lambda: svc.preview_change(admin, "rooms.booking", value=False, reason="short", expected_version=0)) == "FEATURE_VALUE_INVALID"
    assert code(lambda: svc.preview_change(admin, "chat.verbatim_skip", value="weird", reason="x" * 12, expected_version=0)) == "FEATURE_VALUE_INVALID"
    assert code(lambda: svc.preview_change(admin, "rooms.booking", value=False, reason="x" * 12, expected_version=0, expires_at="2020-01-01T00:00:00Z")) == "FEATURE_VALUE_INVALID"
    assert code(lambda: svc.preview_change(admin, "policy.impact", value=True, reason="x" * 12, expected_version=0)) == "FEATURE_DEPENDENCY_OFF"
    pv = svc.preview_change(admin, "rooms.booking", value=False, reason="Bảo trì phòng tầng 3", expected_version=0)
    assert "data_kept" in pv["impact"] and pv["change"]["from"] is True
    assert code(lambda: svc.confirm_change(admin, pv["preview_id"], "", "i1")) == "CONFIRMATION_REQUIRED"
    assert code(lambda: svc.confirm_change(admin, pv["preview_id"], "wrong", "i1")) == "CONFIRMATION_REQUIRED"
    first = svc.confirm_change(admin, pv["preview_id"], pv["confirmation_token"], "i1")
    again = svc.confirm_change(admin, pv["preview_id"], pv["confirmation_token"], "i1")
    assert first["receipt_id"] == again["receipt_id"] and again["replayed"] and svc.version() == 1
    assert code(lambda: svc.confirm_change(admin, pv["preview_id"], pv["confirmation_token"], "i2")) == "PREVIEW_EXPIRED"
    assert code(lambda: svc.preview_change(admin, "rooms.booking", value=True, reason="x" * 12, expected_version=0)) == "FEATURE_VERSION_CONFLICT"
    # removal returns to the lower source and is audited, nothing deleted from the audit
    rm = svc.preview_change(admin, "rooms.booking", reason="Gỡ ghi đè sau bảo trì", expected_version=1, remove=True)
    svc.confirm_change(admin, rm["preview_id"], rm["confirmation_token"], "i3")
    assert svc.enabled("rooms.booking")
    audit = svc.audit(admin, "rooms.booking", None)["items"]
    assert [a["after"].get("removed") for a in audit] == [True, None] and len(audit) == 2


def test_cascade_in_preview_and_expired_preview(tmp_path):
    admin = person()
    clock = [NOW]
    svc = make(tmp_path, clock=lambda: clock[0])
    pv = svc.preview_change(admin, "notifications.inbox", value=False, reason="Tạm dừng hộp thư", expected_version=0)
    assert "reminders.exam" in pv["impact"]["also_off"]
    clock[0] = NOW + timedelta(minutes=11)
    with pytest.raises(OpsError) as caught:
        svc.confirm_change(admin, pv["preview_id"], pv["confirmation_token"], "i")
    assert caught.value.code == "PREVIEW_EXPIRED"


def test_second_process_sees_change_within_three_seconds(tmp_path):
    clock = [0.0]
    a = make(tmp_path, monotonic=lambda: clock[0])
    b = FeatureService(store=FeatureStore(tmp_path / "ff.sqlite3"), clock=lambda: NOW, monotonic=lambda: clock[0])
    assert b.enabled("rooms.booking")
    change(a, person(), "rooms.booking", False)
    clock[0] = 1.0
    assert b.enabled("rooms.booking")  # inside the 2 s cache window
    clock[0] = 2.5
    assert not b.enabled("rooms.booking")  # <= 3 s


def test_unknown_profile_key_is_a_startup_error(tmp_path):
    with pytest.raises(ValueError):
        FeatureService(profile_values={"nope.nope": True})


def test_snapshot_hides_server_only_flags_and_reasons(tmp_path):
    snap = make(tmp_path).snapshot(client_only=True)
    assert "chat.answer_cache" not in snap["features"] and snap["features"]["chat.assistant"] is True
    assert set(snap) == {"version", "features"}


def test_summary_counts_for_the_ops_page(tmp_path):
    svc = make(tmp_path, wired=frozenset())
    base = svc.summary()
    assert base["overrides"] == 0 and base["restart_required"] >= 1 and base["store_error"] is False
    change(svc, person(), "rooms.booking", False)
    after = svc.summary()
    assert after["overrides"] == 1 and after["off"] == base["off"] + 1
