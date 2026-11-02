"""Exclusive SSD writes; artifacts are immutable and orphan files are retained."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from campus247.application.knowledge.platform_models import MAX_UPLOAD, PlatformError


from campus247.application.knowledge.values import StoredArtifact, checked_path  # noqa: E402,F401 -- re-exported


def validate_signature(prefix: bytes, count: int, media_type: str):
    if not count:
        raise PlatformError(422, "EMPTY_FILE", "Tệp không có nội dung.")
    if media_type == "application/pdf" and not prefix.startswith(b"%PDF-"):
        raise PlatformError(422, "MIME_MISMATCH", "Nội dung không phải PDF.")
    if media_type == "text/plain":
        try:
            import codecs
            codecs.getincrementaldecoder("utf-8-sig")().decode(prefix, final=count <= len(prefix))
            if b"\x00" in prefix or prefix.startswith(b"%PDF-"):
                raise ValueError
        except (ValueError, UnicodeError):
            raise PlatformError(422, "MIME_MISMATCH", "TXT cần nội dung UTF-8 hợp lệ.") from None


class FileKnowledgeStorage:
    def __init__(self, workspace: Path, root: Path):
        self.workspace = workspace.absolute()
        self.root = checked_path(root, self.workspace)

    def path(self, key: str) -> Path:
        # Server generated keys only. Reject traversal before canonicalization.
        if len(key) != 36 or any(c not in "0123456789abcdef-" for c in key):
            raise ValueError("Invalid artifact key")
        candidate = checked_path(self.root / key, self.workspace)
        if candidate.parent != self.root:
            raise ValueError("Artifact outside storage root")
        return candidate

    async def receive(self, upload, media_type: str) -> StoredArtifact:
        identifier = str(uuid4())
        target = self.path(identifier)
        self.root.mkdir(parents=True, exist_ok=True)
        checked_path(self.root, self.workspace)
        checksum, count, prefix = hashlib.sha256(), 0, bytearray()
        # Never overwrite, rename or delete even an incomplete original.
        with target.open("xb") as stream:
            while chunk := await upload.read(64 * 1024):
                count += len(chunk)
                if count > MAX_UPLOAD:
                    raise PlatformError(413, "UPLOAD_TOO_LARGE", "Tệp vượt giới hạn 50 MB; bản ghi dở được giữ để kiểm tra.")
                prefix.extend(chunk[:max(0, 4096 - len(prefix))])
                checksum.update(chunk)
                stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        validate_signature(bytes(prefix), count, media_type)
        return StoredArtifact(identifier, identifier, checksum.hexdigest(), count, media_type, "original")

    def write_json(self, value: bytes, kind: str) -> StoredArtifact:
        return self.write_bytes(value, kind, "application/json")

    def write_bytes(self, value: bytes, kind: str, media_type: str) -> StoredArtifact:
        if len(value) > 100 * 1024 * 1024:
            raise PlatformError(422, "ARTIFACT_LIMIT", "Artifact vượt giới hạn xử lý.")
        identifier = str(uuid4())
        target = self.path(identifier)
        self.root.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        return StoredArtifact(identifier, identifier, hashlib.sha256(value).hexdigest(), len(value), media_type, kind)

    def read(self, row) -> bytes:
        path = self.path(row["object_key"])
        if path.stat().st_size != row["byte_size"] or row["byte_size"] > 100 * 1024 * 1024:
            raise PlatformError(409, "ARTIFACT_INTEGRITY", "Không thể xác minh artifact.")
        value = path.read_bytes()
        if hashlib.sha256(value).hexdigest() != row["sha256"]:
            raise PlatformError(409, "ARTIFACT_INTEGRITY", "Không thể xác minh artifact.")
        return value

    def copy_original(self, source: Path, expected_sha256: str, media_type: str) -> StoredArtifact:
        source = checked_path(source, self.workspace)
        if source.stat().st_size > MAX_UPLOAD:
            raise PlatformError(413, "IMPORT_FILE_LIMIT", "Nguồn vượt 50 MB; cần đối chiếu/chia lô riêng.")
        identifier = str(uuid4())
        target = self.path(identifier)
        self.root.mkdir(parents=True, exist_ok=True)
        checksum, count = hashlib.sha256(), 0
        with source.open("rb") as original, target.open("xb") as output:
            while chunk := original.read(64 * 1024):
                count += len(chunk)
                if count > MAX_UPLOAD:
                    raise PlatformError(413, "IMPORT_FILE_LIMIT", "Nguồn vượt giới hạn; file dở được giữ.")
                checksum.update(chunk)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if checksum.hexdigest() != expected_sha256:
            raise PlatformError(409, "IMPORT_ORIGINAL_CHECKSUM", "Nguồn thay đổi so với inventory; dừng phiên bản này.")
        return StoredArtifact(identifier,identifier,checksum.hexdigest(),count,media_type,"original")


class ReadThroughKnowledgeStorage(FileKnowledgeStorage):
    """A restored DB reads retained immutable artifacts and appends into a new scope.

    Existing keys are never rewritten: all inherited writes retain the exclusive
    open contract. Even a generated-key collision fails rather than replacing data.
    """
    def __init__(self, workspace: Path, root: Path, retained_root: Path):
        super().__init__(workspace, root)
        self.retained = FileKnowledgeStorage(workspace, retained_root)

    def path(self, key: str) -> Path:
        target = super().path(key)
        if target.exists():
            return target
        retained = self.retained.path(key)
        return retained if retained.is_file() else target
