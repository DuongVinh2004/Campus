"""F8.1: one PNG in, text out. The image is checked, handled in a private temp folder, and always deleted; nothing is stored."""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import tempfile
import time
import zlib
from collections import defaultdict, deque
from pathlib import Path
from typing import Callable, Protocol

from campus247.ports.campus_ops import OpsError

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_BYTES = 4 * 1024 * 1024
MAX_SIDE = 2000
MIN_SIDE = 16
MAX_TEXT = 2000
DAILY_LIMIT = 20
LOW_CONFIDENCE = 0.6
TIMEOUT_S = 15


class OcrEngine(Protocol):
    def recognize(self, png_path: Path, *, timeout_s: float) -> list[dict]: ...


class OcrUnavailable(Exception):
    pass


class OcrTimeout(Exception):
    pass


def inspect_png(data: bytes) -> tuple[int, int]:
    """Validate signature, a well-formed IHDR, sane dimensions and the first chunk CRCs. Returns (width, height)."""
    if len(data) > MAX_BYTES:
        raise OpsError(413, "IMAGE_TOO_LARGE", "Ảnh lớn hơn 4 MB.")
    if len(data) < 33 or not data.startswith(PNG_SIGNATURE):
        raise OpsError(415, "IMAGE_NOT_PNG", "Chỉ nhận ảnh PNG.")
    length, kind = struct.unpack(">I4s", data[8:16])
    if kind != b"IHDR" or length != 13:
        raise OpsError(415, "IMAGE_NOT_PNG", "Ảnh PNG không hợp lệ.")
    width, height = struct.unpack(">II", data[16:24])
    if zlib.crc32(data[12:29]) & 0xFFFFFFFF != struct.unpack(">I", data[29:33])[0]:
        raise OpsError(415, "IMAGE_NOT_PNG", "Ảnh PNG không hợp lệ.")
    if not (MIN_SIDE <= width <= MAX_SIDE and MIN_SIDE <= height <= MAX_SIDE):
        raise OpsError(422, "IMAGE_DIMENSIONS", f"Kích thước ảnh phải từ {MIN_SIDE} đến {MAX_SIDE} điểm ảnh mỗi cạnh.")
    # walk chunks: IEND must exist and every chunk must fit; guards against a truncated or padded file
    pos, seen_end = 8, False
    while pos + 12 <= len(data):
        n, ctype = struct.unpack(">I4s", data[pos:pos + 8])
        if pos + 12 + n > len(data):
            raise OpsError(415, "IMAGE_NOT_PNG", "Ảnh PNG bị cắt dở.")
        if ctype == b"IEND":
            seen_end = True
            break
        pos += 12 + n
    if not seen_end:
        raise OpsError(415, "IMAGE_NOT_PNG", "Ảnh PNG bị cắt dở.")
    return width, height


def parse_tsv(tsv: str) -> list[dict]:
    """Tesseract TSV -> lines {text, confidence 0..1, bbox [x, y, w, h]}; words are merged per (block, paragraph, line)."""
    lines: dict[tuple, dict] = {}
    for row in tsv.splitlines()[1:]:
        cols = row.split("\t")
        if len(cols) < 12 or cols[0] != "5":
            continue
        text = cols[11].strip()
        try:
            conf = float(cols[10])
        except ValueError:
            continue
        if not text or conf < 0:
            continue
        key = tuple(cols[2:5])
        x, y, w, h = (int(cols[i]) for i in range(6, 10))
        cur = lines.setdefault(key, {"words": [], "conf": [], "box": [x, y, x + w, y + h]})
        cur["words"].append(text)
        cur["conf"].append(conf / 100.0)
        b = cur["box"]
        b[:] = [min(b[0], x), min(b[1], y), max(b[2], x + w), max(b[3], y + h)]
    return [{"text": " ".join(v["words"]), "confidence": round(sum(v["conf"]) / len(v["conf"]), 3),
             "bbox": [v["box"][0], v["box"][1], v["box"][2] - v["box"][0], v["box"][3] - v["box"][1]]} for v in lines.values()]


class TesseractCliEngine:
    """Local Tesseract executable, Vietnamese, no network. Configured by CAMPUS247_INPUT_OCR_TESSERACT (+ optional TESSDATA_PREFIX)."""

    def __init__(self, exe: str | None = None, tessdata: str | None = None, language: str = "vie"):
        self.exe = exe or os.environ.get("CAMPUS247_INPUT_OCR_TESSERACT")
        self.tessdata = tessdata or os.environ.get("TESSDATA_PREFIX")
        self.language = language

    def recognize(self, png_path: Path, *, timeout_s: float) -> list[dict]:
        if not self.exe or not Path(self.exe).is_file():
            raise OcrUnavailable("tesseract executable not configured")
        env = {k: v for k, v in os.environ.items() if k.upper() not in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}}
        if self.tessdata:
            env["TESSDATA_PREFIX"] = self.tessdata
        try:
            done = subprocess.run([self.exe, str(png_path), "stdout", "-l", self.language, "tsv"], capture_output=True, text=True, encoding="utf-8",
                timeout=timeout_s, env=env, cwd=str(png_path.parent))
        except subprocess.TimeoutExpired:
            raise OcrTimeout("ocr timeout") from None
        except OSError:
            raise OcrUnavailable("tesseract failed to start") from None
        if done.returncode != 0:
            raise OcrUnavailable("tesseract returned an error")
        return parse_tsv(done.stdout)


class ImageOcrService:
    def __init__(self, engine: OcrEngine, *, temp_root: Path | None = None, clock: Callable[[], float] = time.time, daily_limit: int = DAILY_LIMIT):
        self.engine, self.clock, self.daily_limit = engine, clock, daily_limit
        self.temp_root = Path(temp_root) if temp_root else None
        self._hits: dict[str, deque] = defaultdict(deque)

    def _limit(self, subject: str) -> None:
        now, window = self.clock(), self._hits[subject]
        while window and now - window[0] > 86400:
            window.popleft()
        if len(window) >= self.daily_limit:
            raise OpsError(429, "IMAGE_RATE", "Bạn đã dùng hết lượt đọc ảnh hôm nay.")
        window.append(now)

    def ocr(self, subject_id: str, png: bytes) -> dict:
        inspect_png(png)
        self._limit(subject_id)
        if self.temp_root:
            self.temp_root.mkdir(parents=True, exist_ok=True)
        workdir = Path(tempfile.mkdtemp(prefix="img-", dir=self.temp_root))
        try:
            path = workdir / "in.png"
            path.write_bytes(png)
            try:
                lines = self.engine.recognize(path, timeout_s=TIMEOUT_S)
            except OcrTimeout:
                raise OpsError(504, "OCR_TIMEOUT", "Đọc ảnh quá lâu, hãy thử ảnh nhỏ hơn.") from None
            except OcrUnavailable:
                raise OpsError(503, "OCR_UNAVAILABLE", "Chức năng đọc ảnh chưa sẵn sàng.") from None
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        text = "\n".join(line["text"] for line in lines)
        warnings = []
        if len(text) > MAX_TEXT:
            text, warnings = text[:MAX_TEXT], warnings + ["TEXT_TRUNCATED"]
        mean = round(sum(line["confidence"] for line in lines) / len(lines), 3) if lines else 0.0
        if not lines or mean < LOW_CONFIDENCE:
            warnings.append("LOW_CONFIDENCE")
        return {"text": text, "lines": lines, "mean_confidence": mean, "warnings": warnings}
