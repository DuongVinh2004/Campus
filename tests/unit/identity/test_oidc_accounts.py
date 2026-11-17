"""Mapping a verified ID token to an account, and the one-time login attempts."""
import sqlite3
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from fake_oidc_provider import CLIENT_ID, ISSUER, REDIRECT  # noqa: E402

from campus247.domain.shared.values import is_valid_uuid7  # noqa: E402
from campus247.infrastructure.identity.oidc import OidcConfig, OidcError  # noqa: E402
from campus247.infrastructure.identity.oidc_accounts import OidcAccountStore, resolve_account, safe_next, validate_config  # noqa: E402
from campus247.ports.identity import IdentityRole  # noqa: E402

NOW = datetime(2026, 11, 17, 3, 0, tzinfo=UTC)
ROLE_MAP = {"sinhvien": "STUDENT", "giangvien": "LECTURER"}


def config(**over):
    return OidcConfig(issuer=ISSUER, client_id=CLIENT_ID, redirect_uri=REDIRECT, **({"role_map": ROLE_MAP} | over))


@pytest.fixture
def store(tmp_path):
    return OidcAccountStore(tmp_path / "oidc.sqlite3")


def claims(**over):
    return {"sub": "user-123", "name": "Nguyễn Văn A", "student_id": "20215678", "groups": ["sinhvien"]} | over


def fails(cfg, store, token_claims, code):
    with pytest.raises(OidcError) as failure:
        resolve_account(cfg, store, token_claims, now=NOW)
    assert failure.value.code == code


class TestResolveAccount:
    def test_an_unknown_person_is_refused_by_default(self, store):
        fails(config(), store, claims(), "ACCOUNT_NOT_PROVISIONED")

    def test_jit_provisioning_creates_a_stable_uuid7_subject(self, store):
        first = resolve_account(config(jit_provisioning=True), store, claims(), now=NOW)
        again = resolve_account(config(jit_provisioning=True), store, claims(name="Tên khác"), now=NOW)
        assert is_valid_uuid7(first["subject_id"]) and again["subject_id"] == first["subject_id"]
        assert first["roles"] == (IdentityRole.STUDENT,) and first["student_code"] == "20215678" and first["display_name"] == "Nguyễn Văn A"
        assert again["display_name"] == "Tên khác"

    def test_a_provisioned_person_may_sign_in_without_jit(self, store):
        subject = store.provision(ISSUER, "user-123", now=NOW)
        assert resolve_account(config(), store, claims(), now=NOW)["subject_id"] == subject

    def test_a_disabled_account_is_refused_even_with_jit(self, store):
        store.provision(ISSUER, "user-123", now=NOW)
        store.set_disabled(ISSUER, "user-123", True)
        fails(config(jit_provisioning=True), store, claims(), "ACCOUNT_DISABLED")
        store.set_disabled(ISSUER, "user-123", False)
        assert resolve_account(config(), store, claims(), now=NOW)

    def test_a_student_needs_a_valid_student_code(self, store):
        cfg = config(jit_provisioning=True)
        for bad in (None, "", "12", "abcdefgh", "2021567800000", 20215678):
            fails(cfg, store, claims(student_id=bad), "STUDENT_CODE_INVALID")
        assert resolve_account(cfg, store, claims(student_id="20215678"), now=NOW)["student_code"] == "20215678"

    def test_a_lecturer_needs_no_student_code(self, store):
        account = resolve_account(config(jit_provisioning=True), store, claims(groups=["giangvien"], student_id=None), now=NOW)
        assert account["roles"] == (IdentityRole.LECTURER,) and account["student_code"] is None

    def test_groups_that_are_not_mapped_give_no_role(self, store):
        fails(config(jit_provisioning=True), store, claims(groups=["khach", "admin"]), "ROLE_NOT_MAPPED")
        fails(config(jit_provisioning=True), store, claims(groups=None), "ROLE_NOT_MAPPED")

    def test_the_groups_claim_may_be_a_single_string(self, store):
        assert resolve_account(config(jit_provisioning=True), store, claims(groups="sinhvien"), now=NOW)["roles"] == (IdentityRole.STUDENT,)

    def test_a_claim_that_says_admin_never_grants_it(self, store):
        cfg = config(jit_provisioning=True, claims={"student_code": "student_id", "display_name": "name", "roles": "groups"})
        account = resolve_account(cfg, store, claims(groups=["sinhvien", "SYSTEM_ADMIN", "admin"], roles=["SYSTEM_ADMIN"], role="SYSTEM_ADMIN"), now=NOW)
        assert account["roles"] == (IdentityRole.STUDENT,)

    def test_privileged_roles_come_only_from_the_owner_s_list(self, store):
        cfg = config(privileged_subjects=({"sub": "user-123", "roles": ["SYSTEM_ADMIN", "KNOWLEDGE_ADMIN"]},))
        account = resolve_account(cfg, store, claims(groups=["sinhvien"]), now=NOW)  # being listed counts as provisioning
        assert set(account["roles"]) == {IdentityRole.STUDENT, IdentityRole.SYSTEM_ADMIN, IdentityRole.KNOWLEDGE_ADMIN}
        other = resolve_account(config(jit_provisioning=True, privileged_subjects=cfg.privileged_subjects), store, claims(sub="someone-else"), now=NOW)
        assert other["roles"] == (IdentityRole.STUDENT,)

    def test_a_listed_admin_needs_no_student_code_when_they_have_no_student_role(self, store):
        cfg = config(privileged_subjects=({"sub": "boss", "roles": ["SYSTEM_ADMIN"]},))
        account = resolve_account(cfg, store, claims(sub="boss", groups=[], student_id=None), now=NOW)
        assert account["roles"] == (IdentityRole.SYSTEM_ADMIN,) and account["student_code"] is None

    def test_a_privileged_entry_for_another_issuer_does_not_apply(self, store):
        cfg = config(privileged_subjects=({"sub": "user-123", "issuer": "https://other.example", "roles": ["SYSTEM_ADMIN"]},), jit_provisioning=True)
        assert resolve_account(cfg, store, claims(), now=NOW)["roles"] == (IdentityRole.STUDENT,)

    def test_the_display_name_is_trimmed_bounded_and_defaulted(self, store):
        cfg = config(jit_provisioning=True)
        assert resolve_account(cfg, store, claims(name="  " + "x" * 300), now=NOW)["display_name"] == "x" * 120
        assert resolve_account(cfg, store, claims(name="   "), now=NOW)["display_name"] == "Người dùng"
        assert resolve_account(cfg, store, claims(name=None), now=NOW)["display_name"] == "Người dùng"


class TestValidateConfig:
    def test_a_role_map_that_grants_admin_is_refused(self):
        for target in ("SYSTEM_ADMIN", "KNOWLEDGE_ADMIN", "SUPPORT_OFFICER", "KNOWLEDGE_CONTRIBUTOR"):
            with pytest.raises(OidcError) as failure:
                validate_config(config(role_map={"sinhvien": "STUDENT", "quantri": target}))
            assert failure.value.code == "CONFIG_ROLE_NOT_ALLOWED_FROM_PROVIDER"

    def test_unknown_roles_and_bad_entries_are_refused(self):
        with pytest.raises(OidcError, match="CONFIG_ROLE_UNKNOWN"):
            validate_config(config(role_map={"x": "ROOT"}))
        for entry in ({"roles": ["SYSTEM_ADMIN"]}, {"sub": "a", "roles": []}, {"sub": "a", "roles": ["NOPE"]}):
            with pytest.raises(OidcError):
                validate_config(config(privileged_subjects=(entry,)))
        with pytest.raises(OidcError, match="CONFIG_PATTERN_INVALID"):
            validate_config(config(student_code_pattern="(["))

    def test_a_good_configuration_passes(self):
        validate_config(config(privileged_subjects=({"sub": "boss", "roles": ["SYSTEM_ADMIN"]},)))


class TestLoginAttempts:
    def test_an_attempt_is_used_once_with_the_right_state(self, store):
        attempt = store.start_attempt(verifier="v1", next_path="/chat", now=NOW)
        done = store.finish_attempt(attempt["id"], attempt["state"], now=NOW + timedelta(minutes=1))
        assert done == {"nonce": attempt["nonce"], "verifier": "v1", "next_path": "/chat"}
        with pytest.raises(OidcError, match="LOGIN_ATTEMPT_INVALID"):
            store.finish_attempt(attempt["id"], attempt["state"], now=NOW + timedelta(minutes=2))

    def test_wrong_state_unknown_id_and_expiry_are_the_same_refusal(self, store):
        attempt = store.start_attempt(verifier="v", next_path=None, now=NOW)
        for call in (lambda: store.finish_attempt(attempt["id"], "wrong", now=NOW), lambda: store.finish_attempt("nope", attempt["state"], now=NOW),
                     lambda: store.finish_attempt(attempt["id"], attempt["state"], now=NOW + timedelta(minutes=11))):
            with pytest.raises(OidcError) as failure:
                call()
            assert failure.value.code == "LOGIN_ATTEMPT_INVALID"
        # a wrong state does not burn the attempt: the legitimate browser can still finish
        assert store.finish_attempt(attempt["id"], attempt["state"], now=NOW)["next_path"] == "/"

    def test_two_requests_racing_for_the_same_attempt_cannot_both_win(self, store):
        attempt = store.start_attempt(verifier="v", next_path="/", now=NOW)
        outcomes = []

        def go():
            try:
                store.finish_attempt(attempt["id"], attempt["state"], now=NOW)
                outcomes.append("ok")
            except OidcError:
                outcomes.append("refused")

        threads = [threading.Thread(target=go) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert sorted(outcomes) == ["ok"] + ["refused"] * 7

    def test_ids_state_and_nonce_are_unpredictable_and_old_attempts_are_swept(self, store):
        first, second = store.start_attempt(verifier="v", next_path="/", now=NOW), store.start_attempt(verifier="v", next_path="/", now=NOW)
        assert len({first["id"], second["id"], first["state"], second["state"], first["nonce"], second["nonce"]}) == 6
        store.start_attempt(verifier="v", next_path="/", now=NOW + timedelta(hours=3))
        with sqlite3.connect(store.path) as db:
            assert db.execute("SELECT COUNT(*) FROM oidc_login_attempts").fetchone()[0] == 1


@pytest.mark.parametrize(("value", "expected"), [
    ("/chat", "/chat"), ("/knowledge/sources?x=1", "/knowledge/sources?x=1"), (None, "/"), ("", "/"), ("chat", "/"),
    ("//evil.example", "/"), ("https://evil.example", "/"), ("/\\evil.example", "/"), ("/ok\nbad", "/"), ("/" + "a" * 400, "/"), ("javascript:alert(1)", "/"),
])
def test_safe_next_keeps_only_paths_inside_the_site(value, expected):
    assert safe_next(value) == expected
