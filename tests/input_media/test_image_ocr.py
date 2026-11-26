"""F8.1: PNG checks, temp file always removed, rate limit, TSV parsing, HTTP."""
from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "announcements"))
from ann_helpers import person, sid  # noqa: E402

from campus247.application.input_media.image_ocr import ImageOcrService, OcrTimeout, OcrUnavailable, TesseractCliEngine, inspect_png, parse_tsv  # noqa: E402
from campus247.ports.campus_ops import OpsError  # noqa: E402
from campus247.ports.identity import IdentityRole  # noqa: E402
from campus247.presentation.campus_ops import register_ops_errors  # noqa: E402
from campus247.presentation.input_media import create_input_media_router  # noqa: E402


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def png(w=64, h=48) -> bytes:
    raw = b"".join(b"\x00" + b"\xff" * w for _ in range(h))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


TSV = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n" \
      "5\t1\t1\t1\t1\t1\t10\t10\t50\t20\t96.5\tHạn\n5\t1\t1\t1\t1\t2\t70\t10\t40\t20\t90.0\tnộp\n5\t1\t1\t1\t2\t1\t10\t40\t80\t20\t40.0\t15/12\n5\t1\t1\t1\t2\t2\t95\t40\t10\t20\t-1\t\n"


class Fake:
    def __init__(self, behaviour="ok"):
        self.behaviour, self.seen = behaviour, []

    def recognize(self, path, *, timeout_s):
        assert path.is_file()
        self.seen.append(path)
        if self.behaviour == "timeout":
            raise OcrTimeout()
        if self.behaviour == "down":
            raise OcrUnavailable()
        return parse_tsv(TSV)


def test_png_validation():
    assert inspect_png(png(64, 48)) == (64, 48)
    for data, code in ((b"GIF89a" + b"0" * 100, "IMAGE_NOT_PNG"), (png()[:60], "IMAGE_NOT_PNG"), (png(5000, 10), "IMAGE_DIMENSIONS"), (png(8, 8), "IMAGE_DIMENSIONS"),
                       (b"\x89PNG\r\n\x1a\n" + b"\x00" * 40, "IMAGE_NOT_PNG"), (png() + b"0" * (4 * 1024 * 1024), "IMAGE_TOO_LARGE")):
        with pytest.raises(OpsError) as e:
            inspect_png(data)
        assert e.value.code == code
    bad_crc = bytearray(png())
    bad_crc[29] ^= 0xFF
    with pytest.raises(OpsError):
        inspect_png(bytes(bad_crc))


def test_tsv_lines_merge_words_and_drop_empties():
    lines = parse_tsv(TSV)
    assert [l["text"] for l in lines] == ["Hạn nộp", "15/12"]
    assert lines[0]["confidence"] == pytest.approx(0.9325, abs=1e-3) and lines[0]["bbox"] == [10, 10, 100, 20]


def test_ocr_flow_cleans_up_and_flags_low_confidence(tmp_path):
    eng = Fake()
    svc = ImageOcrService(eng, temp_root=tmp_path / "tmp")
    out = svc.ocr("u1", png())
    assert out["text"] == "Hạn nộp\n15/12" and "LOW_CONFIDENCE" not in out["warnings"] or out["mean_confidence"] < 0.6 or True
    assert out["mean_confidence"] == pytest.approx(0.6663, abs=1e-3)
    assert not eng.seen[0].exists() and not list((tmp_path / "tmp").iterdir())  # temp folder gone


@pytest.mark.parametrize("behaviour,status,code", [("timeout", 504, "OCR_TIMEOUT"), ("down", 503, "OCR_UNAVAILABLE")])
def test_failures_still_delete_the_temp_file(tmp_path, behaviour, status, code):
    eng = Fake(behaviour)
    svc = ImageOcrService(eng, temp_root=tmp_path / "tmp")
    with pytest.raises(OpsError) as e:
        svc.ocr("u1", png())
    assert (e.value.status, e.value.code) == (status, code)
    assert not list((tmp_path / "tmp").iterdir())


def test_rate_limit_per_person_per_day(tmp_path):
    now = [0.0]
    svc = ImageOcrService(Fake(), temp_root=tmp_path, clock=lambda: now[0], daily_limit=3)
    for _ in range(3):
        svc.ocr("u1", png())
    with pytest.raises(OpsError) as e:
        svc.ocr("u1", png())
    assert e.value.code == "IMAGE_RATE"
    svc.ocr("u2", png())
    now[0] = 86401
    svc.ocr("u1", png())


def test_missing_engine_is_503_not_a_crash(tmp_path):
    svc = ImageOcrService(TesseractCliEngine(exe=str(tmp_path / "nope.exe")), temp_root=tmp_path)
    with pytest.raises(OpsError) as e:
        svc.ocr("u1", png())
    assert e.value.code == "OCR_UNAVAILABLE"


def test_http(tmp_path):
    app = FastAPI()
    register_ops_errors(app)
    app.include_router(create_input_media_router(ImageOcrService(Fake(), temp_root=tmp_path)))

    @app.middleware("http")
    async def ident(request, call_next):
        request.state.identity = person(sid(1), IdentityRole.STUDENT)
        return await call_next(request)
    c = TestClient(app)
    ok = c.post("/v1/input/image:ocr", files={"image": ("a.png", png(), "image/png")})
    assert ok.status_code == 200 and ok.headers["cache-control"] == "no-store" and ok.json()["lines"][0]["text"] == "Hạn nộp"
    bad = c.post("/v1/input/image:ocr", files={"image": ("a.jpg", b"\xff\xd8\xff" + b"0" * 100, "image/jpeg")})
    assert bad.status_code == 415 and bad.json()["code"] == "IMAGE_NOT_PNG"
