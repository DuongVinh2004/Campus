"""Bind one exact public HUCE iframe to the retained PDF; never replace originals."""
import json
from datetime import UTC, datetime

import httpx

from continue_huce_completion_20261025 import OUT, ROOT, read, save, sha

URL = "https://huce.edu.vn/quy-che-dao-tao-trinh-do-dai-hoc-chuyen-sau-dac-thu-bac-7-cua-truong-dai-hoc-xay-dung-ha-noi"


def main():
    old = read(ROOT / "data/huce-public-20261013/regulations.json")["sources"][0]
    with httpx.Client(trust_env=False, timeout=40, follow_redirects=True) as client:
        article = client.get(URL); article.raise_for_status(); assert str(article.url) == URL
        # Read iframe URLs explicitly, rather than interpreting arbitrary text.
        import re
        frames = re.findall(r'<iframe[^>]+src=["\x27]([^"\x27]+)', article.text)
        assert old["linked_pdf"] in frames
        drive_id = old["linked_pdf"].split("/d/", 1)[1].split("/", 1)[0]
        pdf = client.get("https://drive.google.com/uc", params={"export": "download", "id": drive_id})
        pdf.raise_for_status(); assert pdf.content.startswith(b"%PDF") and len(pdf.content) < 20_000_000
        assert sha(pdf.content) == old["pdf_sha256"], "Current attachment differs; retained source not replaced or attested"
    html_path, pdf_path = OUT / "regulation-publisher-01.html", OUT / "regulation-published-01.pdf"
    with html_path.open("xb") as stream: stream.write(article.content)
    with pdf_path.open("xb") as stream: stream.write(pdf.content)
    save(OUT / "regulation-publication-acquisition-01.json", {"at": datetime.now(UTC), "results": [{
        "publisher_url": URL, "publisher_file": str(html_path.relative_to(ROOT)), "publisher_sha256": sha(article.content),
        "linked_url": old["linked_pdf"], "source_file": str(pdf_path.relative_to(ROOT)), "source_sha256": sha(pdf.content),
        "downloaded_original_matches_retained": True}]})
    print(json.dumps({"acquisition_sha256": sha((OUT/"regulation-publication-acquisition-01.json").read_bytes()),
        "original_matches": True, "publisher_iframe_matches": True}))


if __name__ == "__main__":
    main()
