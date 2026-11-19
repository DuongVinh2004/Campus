"""Scan evidence over a version's life: current-scan gate, daily re-scan with fresh signatures, quarantine.

A file that was clean when uploaded can match a signature published later. So every version that can still be shown
is scanned again at least daily with the newest database. A hit never deletes anything: the version becomes
QUARANTINED (hidden from students at once, content refused for everyone, tickets and notes untouched) and the
instructors are told. Quarantine is terminal for that version; the replacement is a new upload.
"""
import time
from datetime import UTC, datetime, timedelta

from campus247.domain.learning import LearningError
from campus247.domain.shared.values import generate_uuid7

QUARANTINED = "QUARANTINED"
RESCAN_INTERVAL = timedelta(hours=24)
# A scheduled publication waits for a scan this fresh instead of trusting one from days ago.
PUBLICATION_SCAN_MAX_AGE = timedelta(hours=36)
RESCAN_BATCH = 3
RESCAN_BACKOFF_SECONDS = 60.0
EXCLUDED_FROM_RESCAN = {"RETRACTED", QUARANTINED}


def _stamp():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class LearningScanLifecycle:
    rescan_clock = staticmethod(lambda: datetime.now(UTC))

    @property
    def scan_receipts_enabled(self):
        """Receipts only exist for scanners that report them (the daemon); test scanners do not take part."""
        return getattr(self.scanner, "health", None) is not None

    @staticmethod
    def last_scan_at(version):
        return max((r.get("scanned_at", "") for r in version.get("scan_receipts", ())), default="")

    def scan_is_current(self, version, maximum=PUBLICATION_SCAN_MAX_AGE):
        if not self.scan_receipts_enabled:
            return True
        last = self.last_scan_at(version)
        if not last:
            return False
        return datetime.fromisoformat(last.replace("Z", "+00:00")) >= self.rescan_clock() - maximum

    def quarantine_version(self, s, version, *, reason_code, signature=None, database_version=None):
        """Hide a version everywhere without deleting its bytes or any class data."""
        material = s["materials"][version["material_id"]]
        previous = version["publication_state"]
        version.update(publication_state=QUARANTINED, revision=version["revision"] + 1, scheduled_at=None,
                       scan_quarantine={"at": _stamp(), "reason_code": reason_code, "signature": signature,
                                        "database_version": database_version, "previous_state": previous})
        if material["current_published_version_id"] == version["id"]:
            replacement = max((v for v in s["versions"].values()
                               if v["material_id"] == material["id"] and v["id"] != version["id"]
                               and v["publication_state"] == "PUBLISHED" and v["processing_state"] == "READY"),
                              key=lambda v: v["version_no"], default=None)
            material["current_published_version_id"] = replacement["id"] if replacement else None
        for presentation in s["presentations"].values():
            if presentation["version_id"] == version["id"] and presentation["status"] == "ACTIVE":
                presentation.update(status="ENDED", updated_at=_stamp(), sequence=presentation["sequence"] + 1,
                                    revision=presentation["revision"] + 1)
        material["revision"] += 1
        event_id, created = generate_uuid7(), _stamp()
        s.setdefault("outbox", {})[event_id] = {"id": event_id, "event_type": "MATERIAL_QUARANTINED", "version_id": version["id"],
                                                "material_id": material["id"], "created_at": created, "delivered_at": created}
        for member in s["members"].values():
            if member["offering_id"] == material["offering_id"] and member["status"] == "ACTIVE" and member["role"] == "INSTRUCTOR":
                key = generate_uuid7()
                s["notifications"][key] = {"id": key, "event_id": event_id, "event_type": "MATERIAL_QUARANTINED",
                                           "actor_id": member["actor_subject_id"], "offering_id": material["offering_id"],
                                           "session_id": None, "version_id": version["id"], "material_id": material["id"],
                                           "title": material["title"], "read_at": None, "created_at": created, "revision": 1}

    async def rescan_due(self, *, limit=RESCAN_BATCH, interval=RESCAN_INTERVAL):
        """Scan up to `limit` of the versions whose last scan is oldest and older than `interval`."""
        if not self.scan_receipts_enabled or time.monotonic() < getattr(self, "_rescan_wait_until", 0.0):
            return {"scanned": 0, "quarantined": 0}
        cutoff = (self.rescan_clock() - interval).isoformat().replace("+00:00", "Z")
        async with self.repository.transaction() as s:
            due = sorted((self.last_scan_at(v), v["id"]) for v in s["versions"].values()
                         if v["processing_state"] == "READY" and v["publication_state"] not in EXCLUDED_FROM_RESCAN
                         and self.last_scan_at(v) < cutoff)[:limit]
            targets = []
            for _, version_id in due:
                version = s["versions"][version_id]
                keys = [version["storage_key"]]
                view = s["blobs"].get(version.get("view_blob_id") or "")
                if view is not None:
                    keys.append(view["storage_key"])
                targets.append((version_id, keys))
        scanned = quarantined = 0
        for version_id, keys in targets:
            try:
                receipts = [await self.scanner.scan(self.blobs.path(key)) for key in keys]
            except LearningError as failure:
                if failure.status == 422:
                    async with self.repository.transaction() as s:
                        version = s["versions"][version_id]
                        if version["publication_state"] not in EXCLUDED_FROM_RESCAN:
                            self.quarantine_version(s, version, reason_code=failure.code,
                                                    signature=getattr(failure, "signature", None))
                            quarantined += 1
                    continue
                # Daemon down or stale: no verdict. Keep serving what was already cleared, retry later without spinning.
                self._rescan_wait_until = time.monotonic() + RESCAN_BACKOFF_SECONDS
                break
            async with self.repository.transaction() as s:
                version = s["versions"][version_id]
                if version["publication_state"] not in EXCLUDED_FROM_RESCAN:
                    rows = [r.as_dict() if hasattr(r, "as_dict") else dict(r) for r in receipts if r]
                    version["scan_receipts"] = (list(version.get("scan_receipts", ())) + rows)[-10:]
                    scanned += 1
        return {"scanned": scanned, "quarantined": quarantined}
