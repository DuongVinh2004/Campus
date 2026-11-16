"""Opaque server attestation for one reviewed curriculum parent."""
from dataclasses import dataclass


@dataclass(frozen=True)
class VerifiedCurriculumParent:
    source_id: str
    version_id: str
    evidence_sha256: str
    release_id: str
    semesters: tuple[int, ...]
    course_codes: tuple[str, ...]
    elective_groups: tuple[str, ...] = ()

    def binds(self, record) -> bool:
        return (self.source_id == record.source_id and self.version_id == record.document_version_id
            and "sha256:"+self.evidence_sha256 == record.quote_span_hash
            and bool(self.release_id) and self.release_id == record.release_id
            and not record.simulation_label)
