"""Read one PNG with the pinned Tesseract inside the same owned Linux namespace as the learning page OCR (F8.1).

Runs in WSL, started by campus247.application.input_media.image_ocr.WslTesseractEngine. The bundle and bubblewrap are checked
against their pinned SHA-256 first; the image is bound read-only, the sandbox has no network, a fresh tmpfs, a memory, CPU and
time limit, and the whole process tree is owned and stopped. Only the TSV result is written, to the request's output folder.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from accessible_text import OcrCandidateError, scoped_path
from ocr_supervisor import LIMITS, WORKSPACE, bounded_read, check_runtime, run_owned, sandbox_prefix

MAX_PNG_BYTES = 4 * 1024 * 1024
LANGUAGES = {"vie", "vie+eng"}


def execute(request_path: Path) -> dict:
    request_path = scoped_path(request_path, WORKSPACE)
    request = json.loads(bounded_read(request_path, 65536))
    scope = request_path.parent
    bundle = scoped_path(Path(request["runtime"]), WORKSPACE)
    png = scoped_path(Path(request["png"]), WORKSPACE)
    output = scoped_path(scope / "output", WORKSPACE)
    language = request["language"]
    timeout = request.get("timeout_seconds", 15)
    if (not bundle.is_dir() or not output.is_dir() or any(output.iterdir()) or language not in LANGUAGES
            or type(timeout) is not int or not 1 <= timeout <= LIMITS["timeout_seconds"]):
        raise OcrCandidateError("OCR_SANDBOX_REQUEST_INVALID")
    data = bounded_read(png, MAX_PNG_BYTES)
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise OcrCandidateError("OCR_SANDBOX_REQUEST_INVALID")
    check_runtime(bundle, request["pins"])
    prefix = sandbox_prefix(bundle, png, output)          # the image is bound read-only (at /input/source.pdf; the name is unused)
    run_owned(prefix + ["/bundle/usr/bin/tesseract", "/input/source.pdf", "/output/result", "--tessdata-dir",
                        "/bundle/usr/share/tesseract-ocr/5/tessdata", "-l", language, "--psm", "3", "tsv"],
              scope, output, time.monotonic() + timeout)
    bounded_read(output / "result.tsv")
    return {"ok": True, "network_disabled": True, "resource_limits_enforced": True, "owned_tree_terminated": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(execute(args.request)))
    except OcrCandidateError as exc:
        print(json.dumps({"error": exc.code, "retryable": exc.retryable}))
    except (OSError, TypeError, ValueError, KeyError, subprocess.SubprocessError):
        print(json.dumps({"error": "OCR_SANDBOX_UNAVAILABLE", "retryable": False}))
