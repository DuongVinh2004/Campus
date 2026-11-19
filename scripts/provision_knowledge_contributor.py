"""Add a knowledge contributor to a local owner-identity file (the owner runs this; nothing is created automatically).

A contributor may add documents; every document of this role needs a second person's approval before publication.
The generated password goes to a new credentials file next to the identity file (exclusive create, never printed).
The identity file is backed up first and replaced atomically. Existing principals are never changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api/src"))
from campus247.domain.shared.values import generate_uuid7  # noqa: E402


def hash_password(password: str, salt: bytes) -> str:
    return hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()


def provision(identity: Path, username: str, display_name: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", username):
        raise ValueError("username: 3-64 characters a-z 0-9 . _ -")
    directory = json.loads(identity.read_text(encoding="utf-8"))
    taken = {directory["username"], *(entry["username"] for entry in directory.get("contributors", []))}
    if username in taken:
        raise ValueError("username already exists; existing principals are never changed")
    credentials = identity.with_name(f"contributor-{username}-credentials.json")
    if credentials.exists():
        raise ValueError("credentials file already exists")
    password, salt = secrets.token_urlsafe(18), secrets.token_bytes(16)
    entry = {"id": generate_uuid7(), "username": username, "display_name": display_name,
             "salt": salt.hex(), "password_hash": hash_password(password, salt)}
    with credentials.open("x", encoding="utf-8") as stream:
        json.dump({"username": username, "password": password, "role": "KNOWLEDGE_CONTRIBUTOR",
                   "login_url": "/login", "scope": directory["tenant"]}, stream, ensure_ascii=False, indent=2)
    shutil.copy2(identity, identity.with_name(identity.name + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S")))
    directory.setdefault("contributors", []).append(entry)
    staged = identity.with_name(identity.name + ".new")
    staged.write_text(json.dumps(directory, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(staged, identity)
    return credentials


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--identity", type=Path, required=True, help="owner-identity.json of the runtime")
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", default="Người đóng góp tri thức")
    args = parser.parse_args(argv)
    try:
        path = provision(args.identity, args.username, args.display_name)
    except (ValueError, OSError, KeyError) as error:
        print(f"PROVISION_FAILED: {error}", file=sys.stderr)
        return 1
    print(f"Contributor '{args.username}' added. Credentials: {path} (not printed). Restart is not required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
