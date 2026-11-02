"""Pure knowledge-platform values shared by application services and their adapters.

Defined here so application code never imports the infrastructure layer; the adapters re-export them.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from campus247.application.knowledge.platform_models import PlatformError


def public_row(row):
    return json.loads(json.dumps(dict(row), default=str)) if row else None


@dataclass(frozen=True)
class StoredArtifact:
    id: str
    object_key: str
    sha256: str
    byte_size: int
    media_type: str
    kind: str


def checked_path(path: Path, workspace: Path) -> Path:
    workspace = workspace.absolute()
    path = path.absolute()
    if workspace.resolve() != workspace or not path.resolve().is_relative_to(workspace) or path.resolve() == workspace:
        raise ValueError("Storage path must be a child of the authorized workspace")
    for parent in (path, *path.parents):
        if parent.exists() and (parent.is_symlink() or parent.is_junction()
                               or getattr(parent.stat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("Reparse paths are not storage targets")
        if parent == workspace:
            break
    return path.resolve()


def public_document_url(value: str) -> str:
    try:
        url = urlsplit(value)
        host = url.hostname or ""
        allowed = host == "huce.edu.vn" or host.endswith(".huce.edu.vn")
        if (len(value) > 1000 or url.scheme != "https" or not allowed or url.port not in {None, 443}
                or url.username or url.password or url.fragment or "\\" in value
                or any(ord(c) < 33 for c in value)
                or any(k.casefold() in {"token", "access_token", "api_key", "password", "signature", "sig"} for k, _ in parse_qsl(url.query))):
            raise ValueError
    except ValueError:
        raise PlatformError(422, "URL_SOURCE_REVIEW_REQUIRED", "Cần URL HTTPS công khai thuộc HUCE, không chứa thông tin đăng nhập.") from None
    return value


def normalized(text: str) -> str:
    return " ".join("".join(c for c in unicodedata.normalize("NFD", text.lower())
                            if unicodedata.category(c) != "Mn").replace("đ", "d").split())


def stable_id(value: str) -> str:
    digest = hashlib.sha256(value.encode()).hexdigest()
    return f"{digest[:8]}-{digest[8:12]}-7{digest[13:16]}-8{digest[17:20]}-{digest[20:32]}"
