"""Create the one explicitly authorized owner account, preserving any existing one."""
import hashlib
import secrets

from knowledge_platform import ROOT, STATE, TENANT, checked_path, retain
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.local_owner import ISSUER


def provision():
    path = checked_path(STATE / "owner-identity.json", ROOT)
    credentials = checked_path(STATE / "owner-credentials.json", ROOT)
    if path.exists() or credentials.exists():
        raise ValueError("Existing account preserved; no replacement or password reset")
    password, salt = secrets.token_urlsafe(24), secrets.token_bytes(16)
    value = {"issuer": ISSUER, "tenant": TENANT, "owner_id": generate_uuid7(), "agent_id": generate_uuid7(),
             "username": "knowledge-owner", "salt": salt.hex(), "signing_key": secrets.token_hex(32),
             "password_hash": hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex(),
             "authority": "Direct owner instruction in chat 2026-10-23: tạo 1 tài khoản chịu trách nhiệm này, tôi xác nhận",
             "university_identity_verified": False}
    retain(path, value)
    retain(credentials, {"username": value["username"], "password": password,
                         "login_url": "http://127.0.0.1:8015/login", "scope": "Local owner-designated account; not HUCE SSO"})
    print("Owner account created. Credentials retained privately in infra/local/knowledge-platform-20261023/owner-credentials.json; not printed.")


if __name__ == "__main__":
    provision()
