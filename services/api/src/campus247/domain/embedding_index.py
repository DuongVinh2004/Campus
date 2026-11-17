"""Immutable DATA-DIC-035 snapshots; activation is an independent trusted pointer.

This contract does not wire an adapter, infer an active index or certify a model
artifact. Callers must supply independently trusted activation/corpus checksums.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import re
from typing import Protocol, runtime_checkable

from campus247.ports.embedding import EmbeddingProfile, EmbeddingVector, validate_embedding_vector


class EmbeddingIndexMismatchError(ValueError):
    """Fail closed without exposing untrusted metadata or document content."""


@runtime_checkable
class ManifestProfile(Protocol):
    """Approved profile projection; domain never imports its application loader.

    Approval/immutability validation belongs to the trusted profile loader. This
    structural boundary also permits the worker to supply the same projection.
    It is not an active manifest or an activation record.
    """
    profile_version: str
    embedding_model_id: str
    embedding_model_revision: str
    embedding_dimension: int
    normalization: str
    distance_metric: str


class BuildStatus(StrEnum):
    BUILDING = "BUILDING"
    VALIDATING = "VALIDATING"
    READY = "READY"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"
    FAILED = "FAILED"


def _require(condition, message):
    if not condition:
        raise EmbeddingIndexMismatchError(message)


def _identifier(value):
    return type(value) is str and 0 < len(value) <= 128 and value == value.strip()


def _checksum(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None and value != "0" * 64


def _timestamp(value):
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


@dataclass(frozen=True)
class ActiveIndexPointer:
    profile_version: str
    index_version: str
    activated_at: datetime

    def __post_init__(self):
        _require(_identifier(self.profile_version) and _identifier(self.index_version)
                 and _timestamp(self.activated_at), "complete trusted active pointer required")


@dataclass(frozen=True)
class EmbeddingIndexManifest:
    index_version: str
    profile_version: str
    embedding_model_id: str
    embedding_model_revision: str
    artifact_sha256: str
    dimension: int
    normalization: str
    distance_metric: str
    corpus_version: str
    document_count: int
    chunk_count: int
    content_checksum: str
    build_status: BuildStatus
    built_at: datetime
    validated_at: datetime | None = None
    activated_at: datetime | None = None

    def __post_init__(self):
        _require(all(_identifier(v) for v in (self.index_version, self.profile_version,
                     self.embedding_model_id, self.corpus_version)), "manifest identifiers required")
        _require(type(self.embedding_model_revision) is str
                 and re.fullmatch(r"[0-9a-f]{40}", self.embedding_model_revision) is not None,
                 "immutable model revision required")
        _require(_checksum(self.artifact_sha256) and _checksum(self.content_checksum), "manifest checksums required")
        _require(type(self.dimension) is int and self.dimension > 0
                 and all(type(n) is int and n >= 0 for n in (self.document_count, self.chunk_count)),
                 "manifest dimension and counts invalid")
        _require(self.normalization == "l2" and self.distance_metric == "cosine", "manifest metric mismatch")
        _require(isinstance(self.build_status, BuildStatus) and _timestamp(self.built_at), "manifest build metadata invalid")
        _require(self.validated_at is None or (_timestamp(self.validated_at) and self.validated_at >= self.built_at),
                 "manifest validation timestamp invalid")
        _require(self.activated_at is None or (_timestamp(self.activated_at) and self.validated_at is not None
                 and self.activated_at >= self.validated_at), "manifest activation timestamp invalid")
        _require(self.build_status not in (BuildStatus.READY, BuildStatus.ACTIVE) or self.validated_at is not None,
                 "ready manifest requires validation")
        _require(self.build_status != BuildStatus.ACTIVE or self.activated_at is not None,
                 "active snapshot requires activation timestamp")

    def validate_query(self, vector: EmbeddingVector, pointer: ActiveIndexPointer, profile: ManifestProfile,
                       *, expected_corpus_version: str, expected_artifact_sha256: str) -> None:
        _require(isinstance(pointer, ActiveIndexPointer) and isinstance(profile, ManifestProfile),
                 "trusted pointer and approved profile required")
        _require(pointer.index_version == self.index_version and pointer.profile_version == self.profile_version
                 == profile.profile_version, "index or profile mismatch")
        _require(self.build_status in (BuildStatus.READY, BuildStatus.ACTIVE) and self.validated_at is not None
                 and pointer.activated_at >= self.validated_at, "index is not validated for activation")
        _require(_identifier(expected_corpus_version) and self.corpus_version == expected_corpus_version,
                 "corpus mismatch")
        _require(_checksum(expected_artifact_sha256) and self.artifact_sha256 == expected_artifact_sha256,
                 "artifact checksum mismatch")
        actual = (self.embedding_model_id, self.embedding_model_revision, self.dimension,
                  self.normalization, self.distance_metric)
        expected = (profile.embedding_model_id, profile.embedding_model_revision, profile.embedding_dimension,
                    profile.normalization, profile.distance_metric)
        _require(all(type(a) is type(e) and a == e for a, e in zip(actual, expected)), "manifest model or dimension mismatch")
        _require(isinstance(vector, EmbeddingVector) and type(vector.dimension) is int
                 and (vector.model_id, vector.model_revision, vector.dimension, vector.normalization)
                 == (self.embedding_model_id, self.embedding_model_revision, self.dimension, self.normalization),
                 "query model or dimension mismatch")
        validate_embedding_vector(vector.values, EmbeddingProfile(self.embedding_model_id,
                                  self.embedding_model_revision, self.dimension))
