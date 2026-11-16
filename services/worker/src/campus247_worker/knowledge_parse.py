"""Bounded read-only parser subprocess. No OCR is silently substituted for scans."""
from __future__ import annotations

import io
import json
import sys
import unicodedata
from pathlib import Path


def identity():
    import hashlib
    from importlib.metadata import version, PackageNotFoundError
    packages = {}
    for name in ("pypdf", "pdfminer.six"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return {"parser_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "layout_code_sha256": hashlib.sha256(Path(__file__).with_name("knowledge_layout.py").read_bytes()).hexdigest(),
        "table_layout_code_sha256": hashlib.sha256(Path(__file__).with_name("knowledge_table_layout.py").read_bytes()).hexdigest(),
        "packages": packages, "schema": "pages-layout-issues-v3", "python": list(sys.version_info[:3])}


def extract(raw: bytes, media_type: str) -> dict:
    pages, issues = [], []
    if media_type == "text/plain":
        text = raw.decode("utf-8-sig")
        if "\x00" in text:
            raise ValueError("BINARY_TEXT")
        pages = [{"page": None, "text": text}]
    elif media_type == "application/pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw), strict=True)
        if reader.is_encrypted:
            raise ValueError("ENCRYPTED_PDF")
        if not 0 < len(reader.pages) <= 500:
            raise ValueError("PAGE_LIMIT")
        total = 0
        for number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            total += len(text)
            if total > 16_000_000:
                raise ValueError("EXTRACTION_LIMIT")
            pages.append({"page": number, "text": text})
    else:
        raise ValueError("UNSUPPORTED_MEDIA")
    for ordinal, page in enumerate(pages, 1):
        page["text"] = unicodedata.normalize("NFC", page["text"].replace("\r\n", "\n"))
        if len(page["text"].strip()) < 20 or "\ufffd" in page["text"]:
            issues.append({"page": page["page"], "block": ordinal, "code": "TEXT_REQUIRES_REVIEW"})
    return {"pages": pages, "issues": issues, "page_count": len(pages), "processor": "text-pdf-pages-v1"}


def main():
    # No filesystem mutation/network/subprocesses from a parser, including third-party libraries.
    def protect(event, args):
        if event == "open":
            mode, flags = args[1:3]
            if isinstance(mode, str) and any(c in mode for c in "wax+") or isinstance(flags, int) and flags & 0x703:
                raise RuntimeError("PARSER_WRITE_DENIED")
        if event.startswith("socket.") or event in {"subprocess.Popen", "os.remove", "os.rename", "os.rmdir"}:
            raise RuntimeError("PARSER_SIDE_EFFECT_DENIED")
    sys.addaudithook(protect)
    try:
        if sys.argv[1:] == ["--identity"]:
            sys.stdout.buffer.write(json.dumps(identity()).encode())
            return
        path, media = Path(sys.argv[1]), sys.argv[2]
        if path.stat().st_size > 50 * 1024 * 1024:
            raise ValueError("UPLOAD_TOO_LARGE")
        result = extract(path.read_bytes(), media)
        profile = identity()
        if media == "application/pdf" and profile["packages"].get("pdfminer.six"):
            from campus247_worker.knowledge_layout import enrich
            result = enrich(path.read_bytes(), result)
        elif media == "application/pdf":
            # A native header does not establish coverage of image/form objects.
            from pypdf import PdfReader
            for source, page in zip(PdfReader(io.BytesIO(path.read_bytes())).pages, result["pages"], strict=True):
                resources = source.get("/Resources", {})
                objects = resources.get("/XObject", {}) if resources else {}
                if objects:
                    page["layout"] = {"route": "UNCLASSIFIED_GRAPHICS", "semantics_verified": False}
                    result["issues"].append({"page": page["page"], "code": "LAYOUT_ADAPTER_REQUIRED"})
        result["parser_identity"] = profile
        sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode())
    except Exception as error:
        # Input text and third-party exception content never enter error logs.
        import traceback
        frames = traceback.extract_tb(error.__traceback__)
        sys.stdout.buffer.write(json.dumps({"error_code": "DOCUMENT_EXTRACTION_FAILED", "error_type": type(error).__name__,
            "failure_function": frames[-1].name if frames else None, "failure_line": frames[-1].lineno if frames else None,
            "code_frames": [{"module": Path(f.filename).name, "function": f.name, "line": f.lineno} for f in frames[-6:]]}).encode())
        raise SystemExit(2)


if __name__ == "__main__":
    main()
