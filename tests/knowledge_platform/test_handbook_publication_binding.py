import json
from pathlib import Path

import pytest

from campus247.application.knowledge.platform_models import digest
from campus247.infrastructure.knowledge import publication
from campus247.infrastructure.knowledge.publication import same_flipbook_pdf

ROOT = Path(__file__).resolve().parents[2]
PDF = "https://cdnm.heyzine.com/files/uploaded/5d2f740216ed19875eb91dba14196df03e68d363.pdf"
FLIP = "https://heyzine.com/flip-book/5d2f740216.html?#page/2"
VIEWER = f'<script>var f="{PDF}"</script>'


@pytest.mark.parametrize("published,canonical,viewer,valid", [
    (FLIP, PDF, VIEWER, True),
    (FLIP, PDF, "<html>no pdf here</html>", False),
    (FLIP, PDF.replace("5d2f7402", "ffffffff"), VIEWER, False),
    ("https://heyzine.com/flip-book/aaaaaaaaaa.html?#page/2", PDF, VIEWER, False),
    ("https://evil.example/flip-book/5d2f740216.html?#page/2", PDF, VIEWER, False),
    (FLIP, "https://evil.example/files/uploaded/5d2f740216ed19875eb91dba14196df03e68d363.pdf", VIEWER, False),
    (FLIP, PDF.replace("https://", "http://"), VIEWER, False),
    (FLIP, PDF + "?x=1", VIEWER, False),
    (None, PDF, VIEWER, False),
])
def test_flipbook_maps_only_to_the_pdf_the_pinned_viewer_names(published, canonical, viewer, valid):
    assert same_flipbook_pdf(published, canonical, viewer) is valid


def test_pinned_handbook_receipt_matches_retained_official_files():
    raw = (ROOT / publication._HANDBOOK_ACQUISITION).read_bytes()
    assert digest(raw) == publication._HANDBOOK_ACQUISITION_SHA256
    item = json.loads(raw)["results"][0]
    for name, key in (("publisher_file", "publisher_sha256"), ("viewer_file", "viewer_sha256"),
                      ("source_file", "source_sha256")):
        assert digest((ROOT / item[name]).read_bytes()) == item[key]
    assert item["publisher_url"].startswith("https://huce.edu.vn/")
    assert same_flipbook_pdf(item["publisher_link"], item["linked_url"],
                             (ROOT / item["viewer_file"]).read_text(encoding="utf-8", errors="ignore"))
