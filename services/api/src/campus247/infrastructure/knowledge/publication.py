"""Validate retained acquisition evidence before attesting external attachments."""
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

from campus247.application.knowledge.platform_models import digest
from campus247.domain.publication import VerifiedPublication, official_huce_uri
from campus247.infrastructure.knowledge.storage import checked_path

_ACQUISITION = "data/huce-document-pipeline/it-english-acquisition-20261022T145232183582Z.json"
_ACQUISITION_SHA256 = "f0d868939aa8604540c3fc757cff24a84f19bed55a13ba378d1692c427a53d54"
_REGULATION_ACQUISITION = "infra/local/huce-completion-20261025-02/regulation-publication-acquisition-01.json"
_REGULATION_ACQUISITION_SHA256 = "4065e765eedf739f4e580fab6163dacb60c25909aa93bce6080a6394c9cf27e1"
_STEM_ACQUISITION = "infra/local/huce-completion-20261025-02/stem-publication-acquisition-01.json"
_STEM_ACQUISITION_SHA256 = "5e987a7c79c488bce2c0e610fde964593e2abad903f55b31b6ce0124b4359bbf"
_HANDBOOK_ACQUISITION = "infra/local/huce-completion-20261102-01/handbook-publication-acquisition-01.json"
_HANDBOOK_ACQUISITION_SHA256 = "ef890b5a1c0561e32c799dfe1a5a89d51bdab199b61562eb9c6cdacfb5f61f1a"


def same_flipbook_pdf(published, canonical, viewer):
    """A flipbook link maps to its PDF only when the retained viewer page names that exact file.

    The flipbook id must prefix the PDF's content hash, the PDF must sit on the flipbook host's CDN
    under its upload path, and the pinned viewer HTML must contain the exact PDF URL.
    """
    flip = re.fullmatch(r"https://heyzine\.com/flip-book/([a-z0-9]{6,})\.html\?#page/\d+", published or "")
    pdf = re.fullmatch(r"https://cdn[a-z]?\.heyzine\.com/files/uploaded/(?:v3/)?([a-f0-9]{40})\.pdf", canonical or "")
    return bool(flip and pdf and pdf[1].startswith(flip[1]) and canonical in viewer)


def same_published_attachment(published, canonical):
    """Only an explicit pinned receipt can map a preview to its own file view."""
    if published == canonical:
        return True
    identities = []
    for value in (published, canonical):
        try:
            uri = urlsplit(value)
        except ValueError:
            return False
        match = re.fullmatch(r"/file/d/([A-Za-z0-9_-]+)/(?:view|preview)", uri.path)
        if uri.scheme != "https" or uri.netloc != "drive.google.com" or uri.query or uri.fragment or not match:
            return False
        identities.append(match[1])
    return identities[0] == identities[1]


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = set()

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if value and (tag == "iframe" and name == "src" or tag == "a" and name == "href"):
                self.urls.add(value)


async def verified_attachment(platform, conn, row, release_id):
    """Unknown/missing acquisition stays unverified; ordinary evidence still works.

    Publication is additional provenance, never publication approval. Caller has
    already applied the release, independent review, scope and metadata gates.
    Hashes bind the retained official HTML, its exact link and the original PDF.
    No network lookup, arbitrary local path or domain-wide Drive exception.
    """
    root = platform.storage.workspace
    matches = []
    for name, expected_sha256 in ((_ACQUISITION, _ACQUISITION_SHA256),
            (_REGULATION_ACQUISITION, _REGULATION_ACQUISITION_SHA256),
            (_STEM_ACQUISITION, _STEM_ACQUISITION_SHA256),
            (_HANDBOOK_ACQUISITION, _HANDBOOK_ACQUISITION_SHA256)):
        acquisition = checked_path(root / name, root)
        if not acquisition.is_file():
            continue
        raw = acquisition.read_bytes()
        if digest(raw) == expected_sha256:
            matches.extend(item for item in json.loads(raw)["results"] if item["linked_url"] == row["canonical_uri"])
    if len(matches) != 1:
        return None
    item = matches[0]
    if not official_huce_uri(item["publisher_url"]):
        return None
    html = checked_path(root / item["publisher_file"], root).read_bytes()
    if digest(html) != item["publisher_sha256"]:
        return None
    links = _Links()
    links.feed(html.decode("utf-8"))
    published_link = item.get("publisher_link", item["linked_url"])
    if published_link not in links.urls:
        return None
    if not same_published_attachment(published_link, item["linked_url"]):
        if not item.get("viewer_file"):
            return None
        viewer = checked_path(root / item["viewer_file"], root).read_bytes()
        if (digest(viewer) != item.get("viewer_sha256")
                or not same_flipbook_pdf(published_link, item["linked_url"], viewer.decode("utf-8", "ignore"))):
            return None
    version = await platform.repo.version(conn, row["document_version_id"])
    artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2",
                                   version["original_id"], platform.repo.tenant)
    original = platform.storage.read(artifact)
    if (digest(original) != item["source_sha256"] or version["original_sha256"] != item["source_sha256"]
            or digest(row["content_text"].encode()) != row["content_checksum"]):
        return None
    rendition_artifact = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1 AND tenant_id=$2",
        version["rendition_id"], platform.repo.tenant)
    rendition_raw = platform.storage.read(rendition_artifact)
    if digest(rendition_raw) != version["rendition_sha256"]:
        return None
    rendition = json.loads(rendition_raw)
    if (rendition.get("original_sha256") != item["source_sha256"]
            or not any(page["text"] == row["content_text"] for page in rendition.get("pages", []))):
        return None
    return VerifiedPublication(item["publisher_url"], item["linked_url"], str(row["source_id"]),
        str(row["document_version_id"]), row["content_checksum"], item["source_sha256"], release_id)
