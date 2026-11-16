"""Fail-closed Windows adapter for the dedicated WSL/bubblewrap page worker."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from pathlib import Path

from campus247_worker.learning.accessible_text import (
    LANGUAGES,
    MAX_ARTIFACT_BYTES,
    OcrCandidateError,
    OcrPageArtifacts,
    OcrSource,
    PageGeometry,
    scoped_path,
)
from campus247_worker.learning.wsl_sandbox import linux_path

PIN_NAMES = {"pdfinfo", "pdftotext", "pdfimages", "pdftoppm", "tesseract", "vie", "eng", "bubblewrap"}


class WslOcrRunner:
    network_disabled = True
    resource_limits_enforced = True

    def __init__(self, *, workspace: Path, runtime_root: Path, pins: dict[str, str],
                 distribution: str = "Ubuntu", wsl_executable: Path = Path("C:/Windows/System32/wsl.exe")):
        self.workspace = workspace.resolve(strict=True)
        self.runtime_root = scoped_path(runtime_root, self.workspace)
        self.supervisor = scoped_path(Path(__file__).with_name("ocr_supervisor.py"), self.workspace)
        self.executable = wsl_executable.resolve(strict=True)
        if (not self.runtime_root.is_dir() or not self.executable.is_file() or self.executable.name.lower() != "wsl.exe"
                or not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", distribution) or set(pins) != PIN_NAMES
                or not all(isinstance(pin, str) and re.fullmatch(r"[0-9a-f]{64}", pin) for pin in pins.values())):
            raise OcrCandidateError("OCR_SANDBOX_CONFIGURATION_INVALID")
        self.distribution = distribution
        self.pins = dict(pins)
        self.profile = {
            "runner": "wsl-bubblewrap-poppler-tesseract-v1",
            "sha256": self.pins,
            "supervisor_sha256": hashlib.sha256(self.supervisor.read_bytes()).hexdigest(),
            "dpi": 250,
            "max_side": 2700,
            "page_segmentation": 3,
            "closure": "bundle and Ubuntu system libraries mounted read-only",
        }

    async def process(self, source: OcrSource, page: int, scope: Path, language: str) -> OcrPageArtifacts:
        scope = scoped_path(scope, self.workspace)
        if language not in LANGUAGES or not scope.is_dir() or any(scope.iterdir()):
            raise OcrCandidateError("OCR_SANDBOX_REQUEST_INVALID")
        if hashlib.sha256(self.supervisor.read_bytes()).hexdigest() != self.profile["supervisor_sha256"]:
            raise OcrCandidateError("OCR_RUNTIME_HASH_MISMATCH")
        output = scoped_path(scope / "output", self.workspace, must_exist=False)
        output.mkdir(exist_ok=False)
        request = scoped_path(scope / "request.json", self.workspace, must_exist=False)
        with request.open("x", encoding="utf-8") as stream:
            json.dump({
                "source": linux_path(source.path, self.workspace),
                "runtime": linux_path(self.runtime_root, self.workspace),
                "sha256": source.sha256, "byte_size": source.byte_size,
                "page_count": source.page_count, "version_id": source.version_id,
                "page": page, "language": language, "pins": self.pins,
            }, stream)
        process = await asyncio.create_subprocess_exec(
            str(self.executable), "-d", self.distribution, "--exec", "/usr/bin/python3", "-B",
            linux_path(self.supervisor, self.workspace), "--request", linux_path(request, self.workspace),
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        communication = asyncio.create_task(process.communicate())
        try:
            stdout, _ = await asyncio.wait_for(asyncio.shield(communication), 90)
        except (asyncio.CancelledError, TimeoutError):
            await asyncio.shield(self._cancel(scope, process, communication))
            raise
        if process.returncode or len(stdout) > 4096:
            raise OcrCandidateError("OCR_SANDBOX_UNAVAILABLE")
        try:
            result = json.loads(stdout)
            if error := result.get("error"):
                if not re.fullmatch(r"OCR_[A-Z_]{1,60}", error):
                    raise ValueError("error code")
                raise OcrCandidateError(error, retryable=result.get("retryable") is True)
            if not all(result.get(key) is True for key in ("network_disabled", "resource_limits_enforced", "owned_tree_terminated")):
                raise OcrCandidateError("OCR_SANDBOX_UNVERIFIED")
            geometry = PageGeometry(result["width"], result["height"], result["rotation"])
            native = self._verified_output(output / "native.xml", result["native_sha256"])
            if result["ocr"] is None:
                return OcrPageArtifacts(geometry, native)
            ocr = result["ocr"]
            tsv = self._verified_output(output / "result.tsv", ocr["tsv_sha256"])
            self._verified_output(output / "page.png", ocr["raster_sha256"])
            return OcrPageArtifacts(geometry, native, tsv, ocr["width"], ocr["height"], ocr["raster_sha256"])
        except OcrCandidateError:
            raise
        except (KeyError, ValueError, TypeError, AttributeError, OSError) as exc:
            raise OcrCandidateError("OCR_SANDBOX_RESULT_INVALID") from exc

    def _verified_output(self, path: Path, checksum: str) -> bytes:
        path = scoped_path(path, self.workspace)
        if not path.is_file() or path.stat().st_size > MAX_ARTIFACT_BYTES:
            raise OcrCandidateError("OCR_OUTPUT_LIMIT")
        with path.open("rb") as stream:
            value = stream.read(MAX_ARTIFACT_BYTES + 1)
        if len(value) > MAX_ARTIFACT_BYTES or hashlib.sha256(value).hexdigest() != checksum:
            raise OcrCandidateError("OCR_RESULT_BINDING")
        return value

    async def _cancel(self, scope, process, communication):
        marker = scoped_path(scope / "cancel-request.json", self.workspace, must_exist=False)
        with marker.open("x", encoding="utf-8") as stream:
            json.dump({"cancel": True}, stream)
        try:
            stdout, _ = await asyncio.wait_for(asyncio.shield(communication), 15)
            result = json.loads(stdout)
        except TimeoutError as exc:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise OcrCandidateError("OCR_SANDBOX_CANCEL_UNVERIFIED") from exc
        except (ValueError, TypeError) as exc:
            raise OcrCandidateError("OCR_SANDBOX_CANCEL_UNVERIFIED") from exc
        if not isinstance(result, dict) or (
            result.get("error") != "OCR_CANCELLED" and result.get("owned_tree_terminated") is not True
        ):
            raise OcrCandidateError("OCR_SANDBOX_CANCEL_UNVERIFIED")
