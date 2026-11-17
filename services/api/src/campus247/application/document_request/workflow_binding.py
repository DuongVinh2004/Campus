"""Bounded provenance captured by application code, never supplied by a model.

Public snapshot integrity does not establish institutional effective dates,
eligibility, official templates, fees or service levels. No form values stored.
"""
from datetime import datetime, timezone
import hashlib
import json
import re

HASH = re.compile(r"^[0-9a-f]{64}$")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def public_sources(guidance):
    result = []
    for source in guidance["sources"]:
        if (source["id"] not in {"catalog", "procedure"} or not HASH.fullmatch(source["content_sha256"])
                or not HASH.fullmatch(source["source_sha256"]) or not isinstance(source["locator"], str)
                or not 0 < len(source["locator"]) <= 1000 or not 0 < len(source["version"]) <= 100):
            raise ValueError("PUBLIC_SOURCE_INVALID")
        result.append({"source_id": source["id"], "version_id": source["version"], "locator": source["locator"],
            "source_sha256": source["source_sha256"], "rendition_sha256": source["content_sha256"],
            "classification": "public_snapshot", "effective_status": "unknown", "effective_from": None, "effective_until": None})
    if len(result) != 2 or {r["source_id"] for r in result} != {"catalog", "procedure"}:
        raise ValueError("PUBLIC_SOURCE_INVALID")
    return sorted(result, key=lambda row: row["source_id"])


def capture_public_snapshot(guidance):
    sources = public_sources(guidance)
    return {"schema_version": "certificate-guidance-snapshot.v1", "captured_at": datetime.now(timezone.utc).isoformat(),
            "sources": sources, "fingerprint": digest(sources), "institutional_effectivity_verified": False}


def checked_public_snapshot(snapshot, guidance):
    if snapshot.get("schema_version") != "certificate-guidance-snapshot.v1":
        raise ValueError("SOURCE_SNAPSHOT_MISSING")
    if (snapshot.get("institutional_effectivity_verified") is not False
            or snapshot.get("fingerprint") != digest(snapshot.get("sources"))):
        raise ValueError("SOURCE_SNAPSHOT_MISMATCH")
    at = datetime.fromisoformat(snapshot["captured_at"])
    if at.utcoffset() is None:
        raise ValueError("SOURCE_CAPTURE_TIME_INVALID")
    current = public_sources(guidance)
    if snapshot["sources"] != current:
        raise ValueError("PUBLIC_SOURCE_CHANGED_OR_UNAVAILABLE")
    return current
