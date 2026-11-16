"""Server-side attestation of an official publisher's exact attachment."""
from dataclasses import dataclass
from urllib.parse import urlparse


def official_huce_uri(value: str) -> bool:
    try:
        uri = urlparse(value)
        return (uri.scheme == "https" and uri.username is None and uri.password is None
                and uri.port in (None, 443)
                and (uri.hostname == "huce.edu.vn" or (uri.hostname or "").endswith(".huce.edu.vn")))
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class VerifiedPublication:
    """Internal value; never accepted from a request, LLM or serialized source."""
    publisher_uri: str
    attachment_uri: str
    source_id: str
    version_id: str
    evidence_sha256: str
    original_sha256: str
    release_id: str

    def binds(self, record) -> bool:
        return (official_huce_uri(self.publisher_uri)
                and self.attachment_uri == record.canonical_uri
                and self.source_id == record.source_id and self.version_id == record.document_version_id
                and "sha256:" + self.evidence_sha256 == record.quote_span_hash
                and self.release_id == record.release_id and bool(self.release_id)
                and len(self.original_sha256) == 64)
