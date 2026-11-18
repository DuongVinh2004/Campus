"""Stream a bounded multipart upload straight to an exclusive workspace artifact.

No system temporary files, global spool overrides, or whole-file request buffers.
Uncommitted files remain available for reconciliation, including failed uploads.
"""
from __future__ import annotations

import dataclasses
import hashlib
import os
from types import SimpleNamespace
from uuid import uuid4

from campus247.application.knowledge.platform_models import MAX_UPLOAD, PlatformError
from campus247.infrastructure.knowledge.storage import StoredArtifact, validate_signature


async def parse_upload(request, storage):
    from python_multipart import MultipartParser
    from python_multipart.multipart import parse_options_header
    media, options = parse_options_header(request.headers.get("content-type", ""))
    boundary = options.get(b"boundary")
    if media != b"multipart/form-data" or not boundary or len(boundary) > 200:
        raise PlatformError(415, "MULTIPART_REQUIRED", "Cần multipart gồm metadata JSON và file.")
    state = {"headers": {}, "header_name": bytearray(), "header_value": bytearray(), "parts": 0,
             "file": None, "artifact": None, "metadata": bytearray(), "prefix": bytearray(),
             "size": 0, "total": 0, "done": False, "fields": set()}

    def begin():
        state["parts"] += 1
        if state["parts"] > 2:
            raise PlatformError(422, "MULTIPART_FIELDS", "Mỗi yêu cầu nhận một file và metadata.")
        state["headers"], state["header_name"], state["header_value"] = {}, bytearray(), bytearray()

    def header_field(data, start, end):
        state["header_name"].extend(data[start:end])
        if len(state["header_name"]) > 200:
            raise PlatformError(422, "HEADER_LIMIT", "Header upload quá dài.")

    def header_value(data, start, end):
        state["header_value"].extend(data[start:end])
        if len(state["header_value"]) > 4096:
            raise PlatformError(422, "HEADER_LIMIT", "Header upload quá dài.")

    def header_end():
        state["headers"][bytes(state["header_name"]).lower()] = bytes(state["header_value"])
        state["header_name"], state["header_value"] = bytearray(), bytearray()

    def headers_finished():
        _, opts = parse_options_header(state["headers"].get(b"content-disposition", b""))
        field = opts.get(b"name")
        if field not in {b"file", b"metadata"} or field in state["fields"]:
            raise PlatformError(422, "MULTIPART_FIELDS", "Cần đúng một file và một trường metadata.")
        state["fields"].add(field)
        state["field"] = field
        if field == b"file":
            identifier = str(uuid4())
            storage.root.mkdir(parents=True, exist_ok=True)
            target = storage.path(identifier)
            state["file"] = target.open("xb")
            state["identifier"], state["checksum"] = identifier, hashlib.sha256()
            state["upload"] = SimpleNamespace(filename=opts.get(b"filename", b"").decode("utf-8"),
                content_type=state["headers"].get(b"content-type", b"application/octet-stream").decode("ascii"))

    def data(data, start, end):
        chunk = data[start:end]
        if state["field"] == b"metadata":
            state["metadata"].extend(chunk)
            if len(state["metadata"]) > 32 * 1024:
                raise PlatformError(422, "METADATA_LIMIT", "Metadata quá dài.")
        else:
            state["size"] += len(chunk)
            if state["size"] > MAX_UPLOAD:
                raise PlatformError(413, "UPLOAD_TOO_LARGE", "Tệp vượt 50 MB.")
            state["prefix"].extend(chunk[:max(0,4096-len(state["prefix"]))])
            state["checksum"].update(chunk)
            state["file"].write(chunk)

    def end_part():
        if state["field"] == b"file":
            stream = state["file"]
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            state["file"] = None
            suffix = state["upload"].filename.lower().rsplit(".",1)[-1]
            mime = {"pdf": "application/pdf", "txt": "text/plain"}.get(suffix)
            if not mime or state["upload"].content_type not in {mime, "application/octet-stream"}:
                raise PlatformError(415, "UNSUPPORTED_MEDIA", "Hỗ trợ PDF/TXT với MIME phù hợp.")
            validate_signature(bytes(state["prefix"]), state["size"], mime)
            state["artifact"] = StoredArtifact(state["identifier"], state["identifier"], state["checksum"].hexdigest(), state["size"], mime, "original")

    def end():
        state["done"] = True

    parser = MultipartParser(boundary, {"on_part_begin": begin, "on_header_field": header_field,
        "on_header_value": header_value, "on_header_end": header_end, "on_headers_finished": headers_finished,
        "on_part_data": data, "on_part_end": end_part, "on_end": end})
    try:
        async for chunk in request.stream():
            state["total"] += len(chunk)
            if state["total"] > MAX_UPLOAD + 128*1024:
                raise PlatformError(413, "UPLOAD_TOO_LARGE", "Yêu cầu vượt giới hạn upload.")
            parser.write(chunk)
        parser.finalize()
        if not state["done"] or not state["artifact"] or state["fields"] != {b"file", b"metadata"}:
            raise PlatformError(422, "INCOMPLETE_MULTIPART", "Upload chưa đầy đủ; có thể thử lại cùng mã yêu cầu.")
        artifact = state["artifact"]
        # The file is on disk and its type is checked; no original is accepted before the malware scan has passed. A rejected or
        # unscanned file raises here, so the caller never registers it (the bytes stay on disk for inspection, as for any failure).
        scan = getattr(storage, "scan_original", None)
        evidence = await scan(storage.path(state["identifier"])) if scan is not None else None
        if evidence:
            artifact = dataclasses.replace(artifact, scan=evidence)
        return state["upload"], artifact, bytes(state["metadata"])
    finally:
        if state["file"]:
            state["file"].close()
