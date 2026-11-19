"""Exact input, profile and authority boundary regressions; no model calls."""
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from campus247.application.knowledge.platform_models import EMBED_MODEL, EMBED_REVISION, PlatformError, metadata_binding
from campus247.ports.embedding import EmbeddingProfile, InvalidEmbeddingVectorError
from campus247_worker.knowledge_embedding_cache import EmbeddingInputCache


def version():
    row = {"source_id": uuid4(), "title": "Synthetic vector reuse", "owner_unit": "Synthetic publisher",
        "canonical_uri": "urn:test:"+uuid4().hex, "authority_level": 50, "campus_scope": "HUCE",
        "faculty_scope": ["FIT"], "program_scope": ["PUBLIC"], "audiences": ["STUDENT"],
        "effective_from": datetime(2026, 1, 1, tzinfo=UTC), "effective_until": None}
    return {**row, "metadata_sha256": metadata_binding(row)}


def cache(tenant="synthetic", profile=None, config="a"*64):
    from types import SimpleNamespace
    return EmbeddingInputCache(SimpleNamespace(tenant=tenant), None,
        profile or EmbeddingProfile(EMBED_MODEL, EMBED_REVISION, 1024), config, "b"*64)


def test_cache_binding_changes_for_input_tenant_source_metadata_and_profile():
    row, service = version(), cache()
    key = service.binding(row, "001234 exact input")
    assert key == service.binding(row, "001234 exact input")
    assert key != service.binding(row, "001234 changed input")
    assert key != cache("other").binding(row, "001234 exact input")
    assert key != service.binding({**row, "source_id": uuid4()}, "001234 exact input")
    changed = {**row, "audiences": ["KNOWLEDGE_ADMIN"]}
    changed["metadata_sha256"] = metadata_binding(changed)
    assert key != service.binding(changed, "001234 exact input")
    assert key != cache(config="c"*64).binding(row, "001234 exact input")
    assert key != cache(profile=replace(service.profile, model_revision="new")).binding(row, "001234 exact input")
    with pytest.raises(PlatformError, match="EMBEDDING_SCOPE_CHANGED"):
        service.binding({**row, "title": "Changed without rebinding"}, "001234 exact input")


def test_invalid_vector_is_rejected_before_artifact_write():
    service = cache()
    with pytest.raises(InvalidEmbeddingVectorError):
        service.prepare(service.binding(version(), "input"), [float("nan")]*1024)
    with pytest.raises(InvalidEmbeddingVectorError):
        service.prepare(service.binding(version(), "input"), [0.0]*1024)
