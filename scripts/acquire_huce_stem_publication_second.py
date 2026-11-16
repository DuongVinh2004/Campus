"""Pin the public CTSV iframe and exact retained STEM attachment bytes."""
import re
from datetime import UTC, datetime

import httpx

from continue_huce_completion_20261025 import OUT, ROOT, checked, read, save, sha

URL = "https://ctsv.huce.edu.vn/thong-bao-ve-chuong-trinh-hoc-bong-stem-quy-chau-a-nam-hoc-2025-2026-2"
PUBLISHED = "https://drive.google.com/file/d/15aajVthfvwJoRiaBFZvsje03VsAxrXci/preview?"


def main():
    candidate = read(OUT / "stem-section-candidate-03.json")
    canonical = candidate["uri"]
    identifier = PUBLISHED.split("/d/")[1].split("/")[0]
    assert canonical == f"https://drive.google.com/file/d/{identifier}/view"
    with httpx.Client(trust_env=False, timeout=40, follow_redirects=True) as client:
        article = client.get(URL); article.raise_for_status()
        assert str(article.url) == URL
        frames = re.findall(r'<iframe[^>]+src=["\x27]([^"\x27]+)', article.text)
        assert PUBLISHED in frames
        pdf = client.get("https://drive.google.com/uc", params={"export": "download", "id": identifier})
        pdf.raise_for_status()
        assert pdf.content.startswith(b"%PDF") and len(pdf.content) < 20_000_000
        assert sha(pdf.content) == candidate["original_sha256"]
    html_file, pdf_file = checked(OUT / "stem-publisher-01.html"), checked(OUT / "stem-published-01.pdf")
    assert not html_file.exists() and not pdf_file.exists()
    with html_file.open("xb") as stream: stream.write(article.content)
    with pdf_file.open("xb") as stream: stream.write(pdf.content)
    save(OUT / "stem-publication-acquisition-01.json", {"at": datetime.now(UTC), "results": [{
        "publisher_url": URL, "publisher_file": str(html_file.relative_to(ROOT)),
        "publisher_sha256": sha(article.content), "publisher_link": PUBLISHED, "linked_url": canonical,
        "source_file": str(pdf_file.relative_to(ROOT)), "source_sha256": sha(pdf.content),
        "downloaded_original_matches_retained": True,
        "uri_identity": "The exact published preview and canonical view refer to the same Drive file identifier; no other Drive URI authorized"}]})
    print({"acquisition_sha256": sha((OUT / "stem-publication-acquisition-01.json").read_bytes()),
        "publisher_iframe_matches": True, "original_matches": True})


if __name__ == "__main__":
    main()
