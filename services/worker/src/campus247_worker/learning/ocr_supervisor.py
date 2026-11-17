"""Run only allowlisted PDF/OCR commands inside an owned Linux namespace."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import subprocess
import time
from pathlib import Path

from accessible_text import (
    LANGUAGES,
    MAX_ARTIFACT_BYTES,
    MAX_RASTER_PIXELS,
    OcrCandidateError,
    OcrSource,
    PageGeometry,
    native_is_usable,
    scoped_path,
    verify_source,
)
from wsl_supervisor import native_launcher, process_tree, stop_owned, writable_usage

WORKSPACE = Path(__file__).resolve(strict=True).parents[5]
RUNTIME_FILES = {
    "pdfinfo": "usr/bin/pdfinfo",
    "pdftotext": "usr/bin/pdftotext",
    "pdfimages": "usr/bin/pdfimages",
    "pdftoppm": "usr/bin/pdftoppm",
    "tesseract": "usr/bin/tesseract",
    "vie": "usr/share/tesseract-ocr/5/tessdata/vie.traineddata",
    "eng": "usr/share/tesseract-ocr/5/tessdata/eng.traineddata",
}
LIMITS = {"timeout_seconds": 60, "memory_mib": 768, "cpu_seconds": 35, "max_output_bytes": MAX_ARTIFACT_BYTES}
DPI = 250


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_runtime(bundle: Path, pins: dict):
    if set(pins) != {*RUNTIME_FILES, "bubblewrap"} or not all(re.fullmatch(r"[0-9a-f]{64}", pin) for pin in pins.values()):
        raise OcrCandidateError("OCR_SANDBOX_CONFIGURATION_INVALID")
    for key, relative in RUNTIME_FILES.items():
        path = scoped_path(bundle / relative, WORKSPACE)
        if not path.is_file() or file_sha256(path) != pins[key]:
            raise OcrCandidateError("OCR_RUNTIME_HASH_MISMATCH")
    if file_sha256(Path("/usr/bin/bwrap")) != pins["bubblewrap"]:
        raise OcrCandidateError("OCR_RUNTIME_HASH_MISMATCH")


def sandbox_prefix(bundle: Path, source: Path, output: Path) -> list[str]:
    command = [
        "/usr/bin/bwrap", "--unshare-all", "--new-session", "--die-with-parent", "--cap-drop", "ALL",
        "--ro-bind", "/usr/lib", "/usr/lib", "--symlink", "usr/lib", "/lib",
        "--ro-bind-try", "/usr/lib64", "/usr/lib64", "--symlink", "usr/lib64", "/lib64",
        "--ro-bind", "/etc/ld.so.cache", "/etc/ld.so.cache",
        "--ro-bind-try", "/etc/fonts", "/etc/fonts", "--ro-bind-try", "/usr/share/fonts", "/usr/share/fonts",
        "--ro-bind-try", "/usr/share/fontconfig", "/usr/share/fontconfig",
        "--ro-bind-try", "/usr/share/locale", "/usr/share/locale",
        "--ro-bind-try", str(bundle / "usr/share/poppler"), "/usr/share/poppler",
        "--ro-bind", str(bundle), "/bundle", "--ro-bind", str(source), "/input/source.pdf",
        "--bind", str(output), "/output", "--proc", "/proc", "--dev", "/dev",
        "--size", str(32 * 1024**2), "--tmpfs", "/tmp", "--clearenv", "--setenv", "HOME", "/tmp",
        "--setenv", "XDG_CACHE_HOME", "/tmp", "--setenv", "LC_ALL", "C.UTF-8",
        "--setenv", "OMP_THREAD_LIMIT", "1",
        "--setenv", "LD_LIBRARY_PATH", "/bundle/usr/lib/x86_64-linux-gnu:/bundle/usr/lib",
        "--chdir", "/output",
    ]
    return native_launcher(LIMITS) + command


def run_owned(command: list[str], scope: Path, output: Path, deadline: float, stdout=None):
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout or subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True)
    observed = {}
    try:
        while process.poll() is None:
            current = process_tree(process.pid)
            observed.update(current)
            rss = sum(item["rss"] for item in current.values())
            size, files = writable_usage((output,))
            if (scope / "cancel-request.json").exists():
                raise OcrCandidateError("OCR_CANCELLED")
            if time.monotonic() >= deadline:
                raise OcrCandidateError("OCR_TIMEOUT", retryable=True)
            if rss > LIMITS["memory_mib"] * 1024**2 or len(current) > 16:
                raise OcrCandidateError("OCR_RESOURCE_LIMIT")
            if size > 4 * MAX_ARTIFACT_BYTES or files > 8:
                raise OcrCandidateError("OCR_OUTPUT_LIMIT")
            time.sleep(0.04)
        if process.returncode:
            raise OcrCandidateError("OCR_SANDBOX_PROCESS_FAILED")
    finally:
        stop_owned(process, observed)


def parse_page_info(path: Path, page: int, page_count: int) -> PageGeometry:
    value = bounded_read(path, 65536).decode("utf-8", errors="replace")
    count = re.search(r"(?m)^Pages:\s*(\d+)\s*$", value)
    rotation = re.search(rf"(?m)^Page\s+{page}\s+rot:\s*(\d+)\s*$", value)
    crop = re.search(rf"(?m)^Page\s+{page}\s+CropBox:\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*$", value)
    if not count or int(count[1]) != page_count or not crop or not rotation or re.search(r"(?m)^Encrypted:\s*yes", value):
        raise OcrCandidateError("OCR_PAGE_METADATA_INVALID")
    left, bottom, right, top = map(float, crop.groups())
    return PageGeometry(right - left, top - bottom, int(rotation[1]))


def bounded_read(path: Path, limit: int = MAX_ARTIFACT_BYTES) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise OcrCandidateError("OCR_OUTPUT_INVALID")
    with path.open("rb") as stream:
        result = stream.read(limit + 1)
    if len(result) > limit:
        raise OcrCandidateError("OCR_OUTPUT_LIMIT")
    return result


def contains_page_image(raw: bytes, geometry: PageGeometry) -> bool:
    """Choose mixed-page OCR only when a visible raster occupies substantial area."""
    for line in raw.decode("utf-8", errors="replace").splitlines()[2:]:
        fields = line.split()
        if len(fields) < 16 or fields[2] != "image":
            continue
        try:
            width, height, x_ppi, y_ppi = (int(fields[index]) for index in (3, 4, 12, 13))
            if min(width, height, x_ppi, y_ppi) > 0 and width * height * 72**2 >= (
                0.20 * x_ppi * y_ppi * geometry.width * geometry.height
            ):
                return True
        except ValueError:
            continue
    return False


def execute(request_path: Path) -> dict:
    request_path = scoped_path(request_path, WORKSPACE)
    request = json.loads(bounded_read(request_path, 65536))
    scope = request_path.parent
    bundle = scoped_path(Path(request["runtime"]), WORKSPACE)
    source_path = scoped_path(Path(request["source"]), WORKSPACE)
    output = scoped_path(scope / "output", WORKSPACE)
    source = OcrSource(source_path, request["sha256"], request["byte_size"], request["page_count"], request["version_id"])
    page, language = request["page"], request["language"]
    if (not bundle.is_dir() or not output.is_dir() or any(output.iterdir()) or language not in LANGUAGES
            or type(page) is not int or not 1 <= page <= source.page_count <= 500
            or type(source.byte_size) is not int or not 5 <= source.byte_size <= 50 * 1024**2
            or not re.fullmatch(r"[0-9a-f]{64}", source.sha256)):
        raise OcrCandidateError("OCR_SANDBOX_REQUEST_INVALID")
    verify_source(source)
    check_runtime(bundle, request["pins"])
    prefix = sandbox_prefix(bundle, source_path, output)
    deadline = time.monotonic() + LIMITS["timeout_seconds"]
    pages = ["-f", str(page), "-l", str(page)]
    pdf = "/input/source.pdf"
    with (output / "info.txt").open("xb") as stdout:
        run_owned(prefix + ["/bundle/usr/bin/pdfinfo", *pages, "-box", pdf], scope, output, deadline, stdout)
    geometry = parse_page_info(output / "info.txt", page, source.page_count)
    run_owned(prefix + ["/bundle/usr/bin/pdftotext", *pages, "-cropbox", "-bbox-layout", "-enc", "UTF-8",
                        pdf, "/output/native.xml"], scope, output, deadline)
    native_xml = bounded_read(output / "native.xml")
    needs_ocr = not native_is_usable(native_xml)
    if not needs_ocr:
        with (output / "images.txt").open("xb") as stdout:
            run_owned(prefix + ["/bundle/usr/bin/pdfimages", *pages, "-list", pdf], scope, output, deadline, stdout)
        needs_ocr = contains_page_image(bounded_read(output / "images.txt", 512 * 1024), geometry)
    result = {"network_disabled": True, "resource_limits_enforced": True, "owned_tree_terminated": True,
              "width": geometry.width, "height": geometry.height, "rotation": geometry.rotation,
              "native_sha256": hashlib.sha256(native_xml).hexdigest(), "ocr": None}
    if needs_ocr:
        # Cap raster dimensions independently of unusual PDF dimensions or DPI requests.
        max_side = max(1, min(2700, math.ceil(max(geometry.width, geometry.height) * DPI / 72)))
        run_owned(prefix + ["/bundle/usr/bin/pdftoppm", *pages, "-cropbox", "-singlefile", "-scale-to",
                            str(max_side), "-png", pdf, "/output/page"], scope, output, deadline)
        raster = bounded_read(output / "page.png")
        if len(raster) < 24 or raster[:8] != b"\x89PNG\r\n\x1a\n" or raster[12:16] != b"IHDR":
            raise OcrCandidateError("OCR_RASTER_RESULT_INVALID")
        width, height = struct.unpack(">II", raster[16:24])
        if not 0 < width <= max_side or not 0 < height <= max_side or width * height > MAX_RASTER_PIXELS:
            raise OcrCandidateError("OCR_RASTER_LIMIT")
        run_owned(prefix + ["/bundle/usr/bin/tesseract", "/output/page.png", "/output/result", "--tessdata-dir",
                            "/bundle/usr/share/tesseract-ocr/5/tessdata", "-l", language, "--dpi", str(DPI),
                            "--psm", "3", "tsv"], scope, output, deadline)
        tsv = bounded_read(output / "result.tsv")
        result["ocr"] = {"width": width, "height": height, "raster_sha256": hashlib.sha256(raster).hexdigest(),
                         "tsv_sha256": hashlib.sha256(tsv).hexdigest()}
    verify_source(source)
    return result


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
