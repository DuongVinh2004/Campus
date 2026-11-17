"""Explicit local performance overlay; accepted grounding/model profile stays fixed."""
from dataclasses import dataclass, fields

from campus247.application.retrieval.profile import (
    _ACCEPTED,
    RetrievalProfile,
    RetrievalProfileError,
)


@dataclass(frozen=True)
class RuntimeDeadlines:
    revision: str
    native_ms: int = 1000
    adapter_ms: int = 1400
    retrieval_ms: int = 3300
    native_batch_seconds: int = 600
    provider_batch_seconds: int = 600
    controller_seconds: int = 900

    def __post_init__(self):
        if not isinstance(self.revision, str) or not self.revision.strip() or len(self.revision) > 80:
            raise RetrievalProfileError("runtime configuration revision required")
        for field in fields(self):
            if field.name != "revision" and type(getattr(self, field.name)) is not int:
                raise RetrievalProfileError("runtime deadlines require exact integers")
        if not (100 <= self.native_ms <= 3000 and self.native_ms + 200 <= self.adapter_ms <= 5000
                and 2 * self.adapter_ms + 400 <= self.retrieval_ms <= 12000
                and 30 <= self.native_batch_seconds <= 600 and 30 <= self.provider_batch_seconds <= 600
                and max(self.native_batch_seconds, self.provider_batch_seconds) <= self.controller_seconds <= 1200):
            raise RetrievalProfileError("runtime deadline bounds or headroom invalid")

    def apply(self, profile: RetrievalProfile) -> RetrievalProfile:
        return RuntimeRetrievalProfile(**dict(profile.to_dict(), semantic_timeout_ms=self.adapter_ms,
            reranker_timeout_ms=self.adapter_ms, overall_timeout_ms=self.retrieval_ms), runtime_deadlines=self)


@dataclass(frozen=True)
class RuntimeRetrievalProfile(RetrievalProfile):
    runtime_deadlines: RuntimeDeadlines

    def __post_init__(self):
        if not isinstance(self.runtime_deadlines, RuntimeDeadlines):
            raise RetrievalProfileError("typed runtime deadlines required")
        deadlines = {"semantic_timeout_ms": self.runtime_deadlines.adapter_ms,
            "reranker_timeout_ms": self.runtime_deadlines.adapter_ms,
            "overall_timeout_ms": self.runtime_deadlines.retrieval_ms}
        for name, baseline in _ACCEPTED.items():
            expected = deadlines.get(name, baseline)
            actual = getattr(self, name)
            if type(actual) is not type(expected) or actual != expected:
                raise RetrievalProfileError("runtime overlay differs from accepted specification")


def validate_effective_profile(profile: RetrievalProfile) -> None:
    """Reconstruct exact supported types; a subclass cannot override validation."""
    if type(profile) is RetrievalProfile:
        RetrievalProfile.from_mapping(profile.to_dict())
    elif type(profile) is RuntimeRetrievalProfile:
        payload = profile.to_dict()
        payload["runtime_deadlines"] = RuntimeDeadlines(**payload["runtime_deadlines"])
        RuntimeRetrievalProfile.from_mapping(payload)
    else:
        raise RetrievalProfileError("unsupported retrieval configuration type")
