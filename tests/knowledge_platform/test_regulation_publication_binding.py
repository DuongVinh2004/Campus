import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from campus247.application.knowledge.platform_models import digest
from campus247.infrastructure.knowledge.publication import verified_attachment

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [None, "original", "evidence", "uri"])
async def test_regulation_attestation_requires_exact_official_iframe_original_and_reviewed_parent(fault):
    base = ROOT / "infra/local/huce-completion-20261025-02"
    receipt = json.loads((base / "regulation-publication-acquisition-01.json").read_text(encoding="utf-8"))["results"][0]
    candidate = json.loads((base / "regulation-candidate-02.json").read_text(encoding="utf-8"))
    parent = next(p for p in candidate["pages"] if "Điều 13, khoản 3" in p["section"])
    rendition = json.dumps({k:candidate[k] for k in ("original_sha256", "pages")}, ensure_ascii=False).encode()
    original = (ROOT / receipt["source_file"]).read_bytes()
    class Repo:
        tenant = "huce-local-public"
        async def version(self, *_):
            return {"original_id": "original", "original_sha256": receipt["source_sha256"],
                "rendition_id": "rendition", "rendition_sha256": digest(rendition)}
    class Conn:
        async def fetchrow(self, _, identifier, *args):
            return {"id": identifier}
    def read(artifact):
        if artifact["id"] == "rendition": return rendition
        return original + b"changed" if fault == "original" else original
    row = {"canonical_uri": receipt["linked_url"], "document_version_id": "version",
        "source_id": candidate["source_id"], "content_text": parent["text"], "content_checksum": parent["text_sha256"]}
    if fault == "evidence": row.update(content_text="Unreviewed disciplinary assertion.", content_checksum=digest(b"Unreviewed disciplinary assertion."))
    if fault == "uri": row["canonical_uri"] += "other"
    platform = SimpleNamespace(repo=Repo(), storage=SimpleNamespace(workspace=ROOT, read=read))
    attested = await verified_attachment(platform, Conn(), row, "release")
    assert (attested is not None) is (fault is None)
