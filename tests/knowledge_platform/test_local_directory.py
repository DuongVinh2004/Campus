"""Simulated directory accounts log in with their own password and role; they cannot escalate or shadow others."""
import base64
import hashlib
import hmac
import json
import secrets

import pytest

from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.local_directory import ISSUER, SCHEMA, LocalDirectoryIdentityAdapter
from campus247.infrastructure.identity.local_owner import ISSUER as OWNER_ISSUER, LocalOwnerIdentityAdapter
from campus247.infrastructure.identity.local_student import (
    ISSUER as STUDENT_ISSUER, LocalCampusIdentityAdapter, LocalStudentIdentityAdapter)
from campus247.ports.identity import IdentityRole

TENANT = "local-directory-test"


def _account(username, role, password, **extra):
    salt = secrets.token_bytes(16)
    return {"username": username, "role": role, "subject_id": generate_uuid7(), "display_name": username.upper(),
            "salt": salt.hex(), "password_hash": hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex(),
            **extra}


def _write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream)


def _directory(path, accounts, **override):
    value = {"schema": SCHEMA, "issuer": ISSUER, "tenant": TENANT, "simulated": True,
             "university_identity_verified": False, "signing_key": secrets.token_hex(32), "accounts": accounts,
             **override}
    _write(path, value)
    return value


def _setup(root, accounts):
    salt = secrets.token_bytes(16)
    common = {"tenant": TENANT, "salt": salt.hex(), "signing_key": secrets.token_hex(32),
              "password_hash": hashlib.scrypt(b"owner-test-password", salt=salt, n=16384, r=8, p=1).hex()}
    _write(root / "owner.json", {**common, "issuer": OWNER_ISSUER, "username": "owner",
                                 "owner_id": generate_uuid7(), "agent_id": generate_uuid7()})
    _write(root / "student.json", {**common, "schema": "local-student-v1", "issuer": STUDENT_ISSUER,
                                   "username": "student", "subject_id": generate_uuid7(),
                                   "student_code": "LOCAL-STUDENT-001", "role": "STUDENT",
                                   "signing_key": secrets.token_hex(32), "university_identity_verified": False})
    value = _directory(root / "directory.json", accounts)
    adapter = LocalCampusIdentityAdapter(LocalOwnerIdentityAdapter(root / "owner.json", TENANT),
                                         LocalStudentIdentityAdapter(root / "student.json", TENANT),
                                         directory=LocalDirectoryIdentityAdapter(root / "directory.json", TENANT))
    return adapter, value


def _signed(claims, key):
    encoded = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode()
    signature = hmac.new(bytes.fromhex(key), encoded.encode(), hashlib.sha256).digest()
    return encoded + "." + base64.urlsafe_b64encode(signature).decode()


def test_each_directory_account_gets_its_own_role_and_profile(retained_directory):
    adapter, value = _setup(retained_directory, [
        _account("sv.a", "STUDENT", "pw-a", student_code="SIM-66IT01-001", faculty_code="CNTT"),
        _account("sv.b", "STUDENT", "pw-b", student_code="SIM-66XD01-002", faculty_code="XD"),
        _account("nv.a", "SUPPORT_OFFICER", "pw-c", staff_code="SIM-NV-001")])
    a = adapter.resolve_token(adapter.authenticate("sv.a", "pw-a"))
    b = adapter.resolve_token(adapter.authenticate("sv.b", "pw-b"))
    staff = adapter.resolve_token(adapter.authenticate("nv.a", "pw-c"))
    assert a.roles == (IdentityRole.STUDENT,) and a.student_code == "SIM-66IT01-001"
    # Simulated faculties never narrow the public knowledge scope (resolved like the local student).
    assert a.faculty_code is None and b.subject_id != a.subject_id
    assert staff.roles == (IdentityRole.SUPPORT_OFFICER,) and staff.student_code is None
    assert a.subject_id == value["accounts"][0]["subject_id"] and a.issuer == ISSUER
    # Existing single accounts are unchanged.
    assert adapter.resolve_token(adapter.authenticate("owner", "owner-test-password")).has_role(IdentityRole.KNOWLEDGE_ADMIN)
    assert adapter.resolve_token(adapter.authenticate("student", "owner-test-password")).student_code == "LOCAL-STUDENT-001"
    # Lecturers can enrol directory students; officers are not listed as students.
    listed = {row["subject_id"] for row in adapter.learning_directory()}
    assert a.subject_id in listed and staff.subject_id not in listed


def test_wrong_password_other_users_password_and_rate_limit(retained_directory):
    adapter, _ = _setup(retained_directory, [
        _account("sv.a", "STUDENT", "pw-a", student_code="SIM-1"),
        _account("sv.b", "STUDENT", "pw-b", student_code="SIM-2")])
    with pytest.raises(ValueError, match="Invalid credentials"):
        adapter.authenticate("sv.a", "pw-b")
    for _ in range(4):
        with pytest.raises(ValueError, match="Invalid credentials"):
            adapter.authenticate("sv.a", "wrong")
    with pytest.raises(ValueError, match="rate limited"):
        adapter.authenticate("sv.a", "pw-a")
    assert adapter.resolve_token(adapter.authenticate("sv.b", "pw-b")).student_code == "SIM-2"


def test_tokens_cannot_pick_role_subject_or_issuer(retained_directory):
    adapter, value = _setup(retained_directory, [
        _account("sv.a", "STUDENT", "pw-a", student_code="SIM-1"),
        _account("nv.a", "SUPPORT_OFFICER", "pw-c", staff_code="SIM-NV-1")])
    token = adapter.authenticate("sv.a", "pw-a")
    claims = json.loads(base64.urlsafe_b64decode(token.split(".")[0]))
    key = value["signing_key"]
    assert adapter.resolve_token(_signed({**claims, "roles": ["SUPPORT_OFFICER"]}, key)).roles == (IdentityRole.STUDENT,)
    for change in ({"tenant": "other"}, {"sub": generate_uuid7()}, {"exp": claims["iat"] - 1},
                   {"exp": claims["iat"] + 7200}, {"jti": ""}, {"iss": OWNER_ISSUER}):
        with pytest.raises(ValueError):
            adapter.resolve_token(_signed({**claims, **change}, key))
    with pytest.raises(ValueError):
        adapter.resolve_token(_signed(claims, secrets.token_hex(32)))


@pytest.mark.parametrize("override", [
    {"simulated": False}, {"university_identity_verified": True}, {"tenant": "other"}, {"schema": "x"}])
def test_directory_scope_is_checked(retained_directory, override):
    _directory(retained_directory / "d.json", [_account("sv.a", "STUDENT", "p", student_code="SIM-1")], **override)
    with pytest.raises(ValueError):
        LocalDirectoryIdentityAdapter(retained_directory / "d.json", TENANT).directory()


@pytest.mark.parametrize("account", [
    _account("sv.a", "STUDENT", "p", student_code="LOCAL-STUDENT-9"),
    _account("sv.a", "KNOWLEDGE_ADMIN", "p", student_code="SIM-1"),
    _account("nv.a", "SUPPORT_OFFICER", "p")])
def test_invalid_accounts_are_refused(retained_directory, account):
    _directory(retained_directory / "d.json", [account])
    with pytest.raises(ValueError):
        LocalDirectoryIdentityAdapter(retained_directory / "d.json", TENANT).directory()


def test_directory_cannot_shadow_existing_accounts(retained_directory):
    with pytest.raises(ValueError, match="must not replace"):
        _setup(retained_directory, [_account("owner", "STUDENT", "p", student_code="SIM-1")])
