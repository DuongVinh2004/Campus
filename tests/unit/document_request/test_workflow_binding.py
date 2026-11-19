from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

from pydantic import ValidationError
import pytest

from campus247.application.assistance.workflow import AppliedSource
from campus247.application.document_request.workflow_binding import capture_public_snapshot, checked_public_snapshot
from campus247.domain.certificate_workflow import certificate_workflow
from campus247.bootstrap import certificate_demo
from campus247.application.document_request.certificates import CertificateError
from campus247.infrastructure.repositories.sqlite_certificates import ROOT


def guidance():
    return {"sources": [{"id": kind, "version": "fixture-v1", "locator": "Fixture " + kind,
        "source_sha256": hashlib.sha256(b"fixture-pdf").hexdigest(),
        "content_sha256": hashlib.sha256(kind.encode()).hexdigest()} for kind in ["catalog", "procedure"]]}


def test_public_snapshot_preserves_integrity_without_claiming_official_effective_dates():
    original = guidance()
    snapshot = capture_public_snapshot(original)
    refs = checked_public_snapshot(snapshot, original)
    assert snapshot["institutional_effectivity_verified"] is False
    assert all(s["effective_status"] == "unknown" and s["effective_from"] is None for s in refs)
    assert {s["source_id"] for s in refs} == {"catalog", "procedure"}
    assert not any(k in snapshot for k in ["profile", "purpose", "recipient", "content_text"])
    changed = deepcopy(original)
    changed["sources"][0]["content_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="PUBLIC_SOURCE_CHANGED"):
        checked_public_snapshot(snapshot, changed)
    tampered = deepcopy(snapshot)
    tampered["sources"][0]["source_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SNAPSHOT_MISMATCH"):
        checked_public_snapshot(tampered, original)


def test_source_contract_rejects_invented_public_effectivity_and_unbounded_identity():
    source = capture_public_snapshot(guidance())["sources"][0]
    assert AppliedSource.model_validate(source).classification == "public_snapshot"
    for change in [{"effective_from": "2026-10-13T00:00:00+00:00"}, {"effective_status": "demo_interval"},
                   {"source_sha256": "fake"}, {"verified": True}]:
        with pytest.raises(ValidationError):
            AppliedSource.model_validate({**source, **change})


def test_missing_duplicate_source_or_faked_verification_is_rejected():
    source = guidance()
    source["sources"] = [source["sources"][0], source["sources"][0]]
    with pytest.raises(ValueError, match="PUBLIC_SOURCE_INVALID"):
        capture_public_snapshot(source)
    snapshot = capture_public_snapshot(guidance())
    snapshot["institutional_effectivity_verified"] = True
    with pytest.raises(ValueError, match="SNAPSHOT_MISMATCH"):
        checked_public_snapshot(snapshot, guidance())


def test_certificate_template_uses_configured_milestone_and_keeps_mandatory_reviews():
    record = {"document_type": "STUDENT_CERTIFICATE", "created_at": "2026-10-14T00:00:00+00:00", "submitted_at": None}
    definition = certificate_workflow(record)
    assert definition.template.version == "certificate-outcome-demo-v1"
    assert all(r.required for r in definition.mandatory_reviews)
    assert "issuance_authority" in {r.id for r in definition.mandatory_reviews}
    record["created_at"] = "2020-01-01T00:00:00+00:00"
    with pytest.raises(ValueError, match="VERSION_UNRESOLVED"):
        certificate_workflow(record)


@pytest.mark.parametrize("pdf,valid",[(b"fixture original PDF",True),(b"wrong PDF",False)])
def test_bootstrap_checks_original_pdf_against_manifest(tmp_path,monkeypatch,pdf,valid):
    assert tmp_path.resolve().is_relative_to(ROOT)
    folder=tmp_path / "data/huce-public-20261013"
    folder.mkdir(parents=True,exist_ok=False)
    corpus={"sources":[{"file":"handbook-2026-2027.pdf","sha256":hashlib.sha256(b"fixture original PDF").hexdigest()}],
        "chunks":[{"page":page,"source_file":"handbook-2026-2027.pdf","title":"Fixture source",
            "url":"https://fixture.invalid/handbook","download_url":"https://fixture.invalid/handbook.pdf","text":"Fixture excerpt"}
            for page in [35,39]]}
    with (folder / "handbook-human-reviewed.json").open("x",encoding="utf-8") as stream:
        json.dump(corpus,stream)
    with (folder / "handbook-2026-2027.pdf").open("xb") as stream:
        stream.write(pdf)
    monkeypatch.setattr(certificate_demo,"ROOT",tmp_path)
    if valid:
        assert all(s["source_sha256"]==hashlib.sha256(pdf).hexdigest() for s in certificate_demo.public_guidance()["sources"])
    else:
        with pytest.raises(CertificateError) as error:
            certificate_demo.public_guidance()
        assert error.value.code=="PUBLIC_SOURCE_HASH_MISMATCH"
