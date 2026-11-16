"""Add official regulations to the retained handbook corpus; no corpus overwrite."""
import hashlib
import io
import json
import re
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from acquire_huce_public_knowledge import DEST, checked

URL = "https://huce.edu.vn/quy-che-dao-tao-trinh-do-dai-hoc-chuyen-sau-dac-thu-bac-7-cua-truong-dai-hoc-xay-dung-ha-noi"


def main():
    sys.path.append(str(Path(sys.base_prefix) / "Lib/site-packages"))
    from pypdf import PdfReader
    if (DEST / "regulations.json").exists():
        raise FileExistsError("retain existing regulations")
    with httpx.Client(timeout=30, verify=ssl.create_default_context(), trust_env=False, follow_redirects=True) as client:
        article = client.get(URL); article.raise_for_status()
        preview = next(x for x in re.findall(r'<iframe[^>]+src=["\x27]([^"\x27]+)', article.text)
                       if x.startswith("https://drive.google.com/file/d/"))
        file_id = preview.split("/d/", 1)[1].split("/", 1)[0]
        response = client.get("https://drive.google.com/uc", params={"export": "download", "id": file_id})
        response.raise_for_status()
        if not response.content.startswith(b"%PDF") or len(response.content) > 20_000_000:
            raise ValueError("bounded official PDF required")
        with checked(DEST / "training-regulations.pdf").open("xb") as stream:
            stream.write(response.content)
        reader = PdfReader(io.BytesIO(response.content))
        chunks = []
        for page, item in enumerate(reader.pages, 1):
            text = item.extract_text() or ""
            text = "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()).strip()
            if text:
                chunks.append({"title": "Quy chế đào tạo HUCE — Quyết định 1486 ngày 06/11/2023",
                    "url": URL, "download_url": preview, "page": page, "section": f"Trang {page}",
                    "text": text, "source_file": "training-regulations.pdf"})
        with checked(DEST / "regulations.json").open("x", encoding="utf-8") as stream:
            json.dump({"acquired_at": datetime.now(timezone.utc).isoformat(), "public_only": True,
                "sources": [{"url": URL, "pdf_sha256": hashlib.sha256(response.content).hexdigest(),
                    "linked_pdf": preview}], "chunks": chunks}, stream, ensure_ascii=False, indent=2)
        print(json.dumps({"regulation_pages": len(reader.pages), "chunks": len(chunks)}))


if __name__ == "__main__":
    main()
