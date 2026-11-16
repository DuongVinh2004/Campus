"""Create new synthetic learning credentials in an exact new workspace directory."""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api/src"))
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.local_learning import ISSUER


def provision(destination: Path, tenant: str, *, second_student: bool = False, pilot_group: bool = False):
    destination = destination.absolute()
    if ".." in destination.parts or not destination.is_relative_to(ROOT):
        raise ValueError("Unambiguous workspace destination required")
    if destination.exists() or destination.resolve().parent != destination.parent.resolve():
        raise ValueError("An exact new directory is required")
    resolved = destination.resolve()
    if resolved == ROOT or not resolved.is_relative_to(ROOT):
        raise ValueError("Learning accounts must remain inside the workspace")
    cursor = destination.parent
    while cursor != ROOT:
        if cursor.is_symlink() or (hasattr(cursor, "is_junction") and cursor.is_junction()):
            raise ValueError("Reparse points are not allowed")
        cursor = cursor.parent
    import re
    if not isinstance(tenant, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", tenant):
        raise ValueError("Explicit configured tenant identifier required")
    accounts, credentials = [], []
    profiles = (
        ("learning-admin", "SYSTEM_ADMIN", "Quản trị học liệu tổng hợp"),
        ("learning-lecturer", "LECTURER", "Giảng viên học liệu tổng hợp"),
        ("learning-student", "STUDENT", "Sinh viên học liệu tổng hợp"),
    )
    if pilot_group:
        profiles = (
            profiles[0],
            ("learning-g01", "LECTURER", "G01 · Giảng viên thử học liệu"),
            ("learning-g02", "LECTURER", "G02 · Giảng viên thử học liệu"),
            *((f"learning-s{index:02d}", "STUDENT", f"S{index:02d} · Sinh viên thử học liệu")
              for index in range(1, 11)),
        )
    elif second_student:
        profiles += (("learning-classmate", "STUDENT", "Bạn cùng lớp học liệu tổng hợp"),)
    for username, role, label in profiles:
        password, salt = secrets.token_urlsafe(24), secrets.token_bytes(16)
        subject = generate_uuid7()
        accounts.append({"username": username, "subject_id": subject, "role": role,
            "display_name": label, "is_synthetic": True, "salt": salt.hex(),
            "password_hash": hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()})
        credentials.append({"username": username, "password": password, "subject_id": subject, "role": role})
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in (
        ("identity.json", {"schema": "local-learning-v1", "issuer": ISSUER, "tenant": tenant,
            "university_identity_verified": False, "signing_key": secrets.token_hex(32), "accounts": accounts}),
        ("credentials.json", {"synthetic_only": True, "accounts": credentials}),
    ):
        with (destination / name).open("x", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
    return {"directory": str(resolved), "accounts_created": len(accounts), "credentials_printed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--tenant", required=True)
    account_scope = parser.add_mutually_exclusive_group()
    account_scope.add_argument("--second-student", action="store_true")
    account_scope.add_argument("--pilot-group", action="store_true")
    args = parser.parse_args()
    print(json.dumps(provision(args.directory, args.tenant, second_student=args.second_student, pilot_group=args.pilot_group)))
