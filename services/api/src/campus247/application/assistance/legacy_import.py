"""Preserving legacy student-chat import. Browser ownership is never evidence."""
import hashlib
import json

from campus247.application.assistance.durable_services import ConfirmedStateService
from campus247.application.assistance.feature_contracts import LegacyImportSnapshot
from campus247.application.assistance.state_storage import digest
from campus247.application.document_request.certificates import CertificateError


class LegacyImportService(ConfirmedStateService):
    namespaces = frozenset({"legacy_import"})

    def __init__(self, *args, ownership=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Trusted deployment input, keyed by exact source bytes. No inference
        # from a localStorage key, display name, claimed owner or demo account.
        self.ownership = dict(ownership or {})

    def inspect(self, actor, source_json):
        scope = self.scope(actor)
        if not isinstance(source_json, str) or len(source_json.encode("utf-8")) > 48000:
            raise CertificateError(422, "LEGACY_TOO_LARGE", "Chia dữ liệu cũ thành snapshot nhỏ hơn")
        try:
            def unique_pairs(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("duplicate JSON key")
                    result[key] = value
                return result
            value = json.loads(source_json, object_pairs_hook=unique_pairs,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid number")))
            if (type(value) is not dict or set(value) - {"version", "threads", "activeId"}
                    or type(value.get("version")) is not int or value["version"] not in (1, 2)):
                raise ValueError("unsupported legacy format")
            threads = value["threads"]
            if not isinstance(threads, list) or not 1 <= len(threads) <= 50:
                raise ValueError("bounded threads required")
            ids, exchanges = set(), 0
            for thread in threads:
                if (type(thread) is not dict or not isinstance(thread.get("id"), str) or not 1 <= len(thread["id"]) <= 100
                        or thread["id"] in ids or not isinstance(thread.get("title"), str) or len(thread["title"]) > 200
                        or not isinstance(thread.get("input"), str) or len(thread["input"]) > 4000
                        or not isinstance(thread.get("exchanges"), list)):
                    raise ValueError("invalid legacy thread")
                ids.add(thread["id"])
                item_ids = set()
                for item in thread["exchanges"]:
                    if (type(item) is not dict or not isinstance(item.get("id"), str) or not 1 <= len(item["id"]) <= 100
                            or item["id"] in item_ids or not isinstance(item.get("question"), str) or len(item["question"]) > 4000
                            or type(item.get("reply")) is not dict or not isinstance(item["reply"].get("text"), str)
                            or len(item["reply"]["text"]) > 12000):
                        raise ValueError("invalid legacy exchange")
                    item_ids.add(item["id"])
                    exchanges += 1
            if exchanges > 200 or value.get("activeId") not in ids:
                raise ValueError("invalid legacy active thread or size")
        except (ValueError, TypeError, KeyError, RecursionError):
            raise CertificateError(422, "LEGACY_FORMAT_INVALID", "Không đọc được snapshot; giữ nguyên dữ liệu nguồn") from None
        source_sha = hashlib.sha256(source_json.encode("utf-8")).hexdigest()
        evidence = self.ownership.get(source_sha)
        if (not isinstance(evidence, dict) or evidence.get("tenant") != scope.tenant or evidence.get("owner") != scope.owner
                or evidence.get("classification") not in {"demo", "verified_owner"} or not evidence.get("evidence_id")):
            raise CertificateError(409, "LEGACY_OWNER_UNVERIFIED", "Chưa có bằng chứng chủ sở hữu từ server; giữ và export nguồn trên thiết bị")
        snapshot = LegacyImportSnapshot(source_json=source_json, source_sha256=source_sha, logical_sha256=digest(value),
            owner_evidence=evidence["evidence_id"], classification=evidence["classification"],
            thread_count=len(threads), exchange_count=exchanges)
        if len(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False).encode()) > 65536:
            raise CertificateError(422, "LEGACY_TOO_LARGE", "Snapshot vượt giới hạn lưu; giữ và chia nhỏ nguồn")
        return snapshot

    def prepare(self, actor, source_json, client_id):
        value = self.inspect(actor, source_json)
        prior = self.store.get(self.scope(actor), "legacy_import", value.logical_sha256)
        if prior is not None:
            # Formatting-only changes cannot duplicate or overwrite the first
            # source bytes/provenance. Return its verified original receipt.
            self.revalidate(actor, "legacy_import", prior.key, prior.payload)
            return {"already_imported": True, "record": self.export(actor, prior.key)}
        return self.preview(actor, "legacy_import", value.logical_sha256, 0, value.model_dump(mode="json"), client_id)

    def revalidate(self, actor, namespace, key, payload):
        value = LegacyImportSnapshot.model_validate(payload)
        if value != self.inspect(actor, value.source_json) or key != value.logical_sha256:
            raise CertificateError(409, "LEGACY_PROVENANCE_CHANGED", "Nguồn hoặc bằng chứng chủ sở hữu đã đổi")

    def export(self, actor, import_id):
        scope = self.scope(actor)
        record = self.store.get(scope, "legacy_import", import_id)
        if record is None:
            raise CertificateError(404, "RESOURCE_NOT_FOUND", "Không tìm thấy bản import")
        self.revalidate(actor, "legacy_import", import_id, record.payload)
        # Retain original text exactly; no executable links/actions/proposals
        # are promoted into conversation history or any model context.
        receipts = self.store.history(scope, "legacy_import", import_id, limit=1)
        return {"import_id": import_id, "snapshot": record.payload, "version": record.version,
                "committed_at": receipts[0].committed_at, "execution_authority": "none"}
