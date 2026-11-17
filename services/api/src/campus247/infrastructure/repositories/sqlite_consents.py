"""Existing consent service port backed by atomic actor state, never a grant."""
from datetime import datetime, timezone

from campus247.application.assistance.state_storage import (StateScope, StateReceipt, StorageUnavailable,
    StorageCorrupt, StorageConflict, digest)
from campus247.application.privacy.consent import ConsentRecord, ServiceUnavailableError, VALID_PURPOSES
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.repositories.sqlite_actor_state import SQLiteActorStateStore
from campus247.ports.identity import IdentityContext


class SQLiteConsentRepository:
    def __init__(self,store,*,tenant):
        if not isinstance(store,SQLiteActorStateStore):
            raise ValueError("typed actor state store required")
        StateScope(tenant,generate_uuid7())
        self.store,self.tenant=store,tenant

    def record_consent(self,actor,purpose,decision,notice_version):
        if (not isinstance(actor,IdentityContext) or not actor.is_synthetic or not actor.is_active
                or actor.expires_at<=datetime.now(timezone.utc) or not actor.session_id or actor.tenant_id!=self.tenant):
            raise ValueError("active server-bound consent identity required")
        scope=StateScope(self.tenant,actor.subject_id)
        payload={"purpose":purpose,"decision":decision,"notice_version":notice_version}
        client_id=generate_uuid7()
        try:
            # Distinct concurrent declarations may race; retry only a rejected
            # CAS, never an uncertain database commit or changed client intent.
            for attempt in range(3):
                current=self.store.get(scope,"consent",purpose)
                try:
                    receipt=self.store.commit(scope,"consent",purpose,current.version if current else 0,payload,client_id)
                    return ConsentRecord(id=receipt.receipt_id,user_id=actor.subject_id,purpose=purpose,decision=decision,
                        notice_version=notice_version,recorded_at=datetime.fromisoformat(receipt.committed_at))
                except StorageConflict as error:
                    if str(error)!="STATE_STALE_VERSION":
                        raise
            raise StorageUnavailable("CONSENT_WRITE_CONFLICT")
        except (StorageUnavailable,StorageCorrupt,StorageConflict):
            raise ServiceUnavailableError("CONSENT_STORAGE_UNAVAILABLE") from None

    def has_active_consent(self,user_id,purpose):
        if purpose not in VALID_PURPOSES:
            raise ValueError("unknown consent purpose")
        try:
            record=self.store.get(StateScope(self.tenant,user_id),"consent",purpose)
            return bool(record and record.payload["purpose"]==purpose and record.payload["decision"]=="GRANTED")
        except (StorageUnavailable,StorageCorrupt):
            raise ServiceUnavailableError("CONSENT_STORAGE_UNAVAILABLE") from None

    def list_user_consents(self,user_id):
        scope=StateScope(self.tenant,user_id)
        try:
            with self.store.connect() as connection:
                rows=connection.execute("SELECT fingerprint,record FROM unified_state_receipt WHERE tenant=? AND owner=? ORDER BY rowid LIMIT 1001",
                    (scope.tenant,scope.owner)).fetchall()
                if len(rows)>1000:
                    raise StorageUnavailable("CONSENT_HISTORY_PAGE_REQUIRED")
                result=[]
                for fingerprint,encoded in rows:
                    try:
                        receipt=StateReceipt.model_validate_json(encoded)
                        if (receipt.tenant,receipt.owner,receipt.fingerprint)!=(scope.tenant,scope.owner,fingerprint) or receipt.is_replay:
                            raise ValueError("receipt column mismatch")
                        if receipt.namespace!="consent":
                            continue
                        revision=connection.execute("SELECT version,record,event_id FROM unified_state_revision WHERE tenant=? AND owner=? AND namespace='consent' AND key=? AND version=?",
                            (scope.tenant,scope.owner,receipt.key,receipt.version)).fetchone()
                        if not revision or revision[2]!=receipt.receipt_id:
                            raise ValueError("consent revision missing")
                        record=self.store._decode(revision[:2],scope,"consent",receipt.key)
                        expected=digest({"tenant":scope.tenant,"owner":scope.owner,"namespace":"consent","key":receipt.key,
                            "expected_version":receipt.version-1,"payload_sha256":record.sha256})
                        if (record.committed_at,record.sha256,expected)!=(receipt.committed_at,receipt.payload_sha256,fingerprint):
                            raise ValueError("consent receipt binding invalid")
                        if record.payload["purpose"]!=receipt.key:
                            raise ValueError("consent purpose binding invalid")
                        result.append(ConsentRecord(id=receipt.receipt_id,user_id=user_id,purpose=record.payload["purpose"],
                            decision=record.payload["decision"],notice_version=record.payload["notice_version"],
                            recorded_at=datetime.fromisoformat(receipt.committed_at)))
                    except (ValueError,TypeError,KeyError):
                        raise StorageCorrupt("CONSENT_RECEIPT_INVALID") from None
                return result
        except (StorageUnavailable,StorageCorrupt):
            raise ServiceUnavailableError("CONSENT_STORAGE_UNAVAILABLE") from None
