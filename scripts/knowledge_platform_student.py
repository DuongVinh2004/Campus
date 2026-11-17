"""Provision the requested local student account without changing any existing identity."""
import hashlib
import secrets

from knowledge_platform import ROOT, STATE, TENANT, checked_path, retain
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.local_student import ISSUER


def provision():
    identity = checked_path(STATE / "student-identity.json", ROOT)
    credentials = checked_path(STATE / "student-credentials.json", ROOT)
    if identity.exists() or credentials.exists():
        raise ValueError("Existing student account preserved; no replacement or password reset")
    salt, password = secrets.token_bytes(16), secrets.token_urlsafe(18)
    value = {"schema":"local-student-v1", "issuer":ISSUER, "tenant":TENANT,
        "subject_id":generate_uuid7(), "role":"STUDENT", "student_code":"LOCAL-STUDENT-001",
        "username":"student-local", "salt":salt.hex(), "signing_key":secrets.token_hex(32),
        "password_hash":hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1).hex(),
        "university_identity_verified":False,
        "authority":"Direct user request for student login in the local project, 2026-10-27"}
    retain(identity,value)
    retain(credentials,{"username":value["username"],"password":password,
        "login_url":"http://127.0.0.1:8015/login", "scope":"Local student testing; public knowledge and own conversations only; not HUCE SSO"})
    print("Local student account created. Credentials retained in student-credentials.json; password not printed.")


if __name__ == "__main__":
    provision()
