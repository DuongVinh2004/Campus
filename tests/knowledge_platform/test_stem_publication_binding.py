import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from campus247.application.knowledge.platform_models import digest
from campus247.infrastructure.knowledge.publication import same_published_attachment, verified_attachment

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("canonical,valid", [
    ("https://drive.google.com/file/d/ABC_12-/view", True),
    ("https://drive.google.com/file/d/OTHER/view", False),
    ("https://drive.google.com/file/d/ABC_12-/view?other=1", False),
    ("https://drive.google.com/file/d/ABC_12-/view#fragment", False),
    ("https://drive.google.com.evil.invalid/file/d/ABC_12-/view", False),
    ("https://user@drive.google.com/file/d/ABC_12-/view", False),
    ("https://drive.google.com:443/file/d/ABC_12-/view", False),
    ("http://drive.google.com/file/d/ABC_12-/view", False),
    ("https://drive.google.com/file/d/ABC_12-/download", False),
])
def test_preview_mapping_cannot_transfer_the_publisher_binding_to_another_file(canonical, valid):
    assert same_published_attachment("https://drive.google.com/file/d/ABC_12-/preview?", canonical) is valid


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [None, "original", "evidence", "uri", "rendition"])
async def test_stem_requires_pinned_official_html_exact_file_and_reviewed_form_parent(fault):
    base = ROOT / "infra/local/huce-completion-20261025-02"
    receipt = json.loads((base / "stem-publication-acquisition-01.json").read_text(encoding="utf-8"))["results"][0]
    candidate = json.loads((base / "stem-section-candidate-03.json").read_text(encoding="utf-8"))
    parent = next(p for p in candidate["pages"] if p["page"] == 5)
    rendition = json.dumps({k: candidate[k] for k in ("original_sha256", "pages")}, ensure_ascii=False).encode()
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
        if artifact["id"] == "rendition": return rendition + b"changed" if fault == "rendition" else rendition
        return original + b"changed" if fault == "original" else original
    row = {"canonical_uri": receipt["linked_url"], "document_version_id": "version", "source_id": candidate["source_id"],
        "content_text": parent["text"], "content_checksum": parent["text_sha256"]}
    if fault == "evidence": row.update(content_text="Unreviewed field", content_checksum=digest(b"Unreviewed field"))
    if fault == "uri": row["canonical_uri"] = row["canonical_uri"].replace("15aajVth", "DIFFERENT")
    platform = SimpleNamespace(repo=Repo(), storage=SimpleNamespace(workspace=ROOT, read=read))
    attested = await verified_attachment(platform, Conn(), row, "release")
    assert (attested is not None) is (fault is None)
