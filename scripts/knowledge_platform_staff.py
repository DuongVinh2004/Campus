"""Provision a local support-officer account without changing any existing identity."""
import hashlib
import secrets

from knowledge_platform import ROOT, STATE, TENANT, checked_path, retain
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.local_staff import ISSUER


def provision():
    identity = checked_path(STATE / "staff-identity.json", ROOT)
    credentials = checked_path(STATE / "staff-credentials.json", ROOT)
    if identity.exists() or credentials.exists():
        raise ValueError("Existing staff account preserved; no replacement or password reset")
    salt, password = secrets.token_bytes(16), secrets.token_urlsafe(18)
    value = {"schema": "local-staff-v1", "issuer": ISSUER, "tenant": TENANT,
             "subject_id": generate_uuid7(), "role": "SUPPORT_OFFICER", "staff_code": "LOCAL-STAFF-001",
             "username": "staff-local", "salt": salt.hex(), "signing_key": secrets.token_hex(32),
             "password_hash": hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex(),
             "university_identity_verified": False,
             "authority": "Direct user request to complete the staff workflow in the local project, 2026-11-14"}
    retain(identity, value)
    retain(credentials, {"username": value["username"], "password": password,
                         "login_url": "http://127.0.0.1:8015/login",
                         "scope": "Local staff testing; ticket queue only; not HUCE SSO"})
    print("Local staff account created. Credentials retained in staff-credentials.json; password not printed.")


if __name__ == "__main__":
    provision()
