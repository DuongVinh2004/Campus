"""F8.1 with the real engine: a rendered Vietnamese PNG read by the pinned Tesseract bundle in WSL + bubblewrap.

Opt-in (CAMPUS247_INPUT_OCR_NATIVE=1) because it needs WSL Ubuntu with bubblewrap and the bundle at
CAMPUS247_INPUT_OCR_WSL_RUNTIME (default .tooling/learning-ocr-native-20261117-01). The text is rendered by the test, so the
expected words are known exactly; the check is word-level (OCR may miss a diacritic), and reported, not tuned.
"""
import io
import os
import unicodedata
from pathlib import Path

import pytest

from campus247.application.input_media.image_ocr import ImageOcrService, WslTesseractEngine

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / os.environ.get("CAMPUS247_INPUT_OCR_WSL_RUNTIME", ".tooling/learning-ocr-native-20261117-01")
pytestmark = pytest.mark.skipif(os.environ.get("CAMPUS247_INPUT_OCR_NATIVE") != "1" or not BUNDLE.is_dir(),
                                reason="needs WSL + the pinned OCR bundle; set CAMPUS247_INPUT_OCR_NATIVE=1")
LINES = ["Học phí học kỳ một năm học 2026", "Sinh viên nộp đơn trước ngày 15 tháng 12", "Phòng Đào tạo tiếp nhận hồ sơ"]


def render() -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 36)
    image = Image.new("L", (1100, 260), 255)
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(LINES):
        draw.text((30, 30 + i * 70), line, fill=0, font=font)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold()) if unicodedata.category(c) != "Mn").replace("đ", "d")


def test_a_rendered_vietnamese_image_is_read_inside_the_sandbox(tmp_path):
    temp = ROOT / ".pytest-tmp" / "image-ocr"
    temp.mkdir(parents=True, exist_ok=True)
    service = ImageOcrService(WslTesseractEngine(ROOT, BUNDLE), temp_root=temp)
    result = service.ocr("synthetic-student", render())
    words = [w for line in LINES for w in line.split()]
    exact = sum(1 for w in words if w in result["text"])
    loose = sum(1 for w in words if fold(w) in fold(result["text"]))
    print(f"words exact {exact}/{len(words)}, without diacritics {loose}/{len(words)}, mean confidence {result['mean_confidence']}")
    assert loose / len(words) >= 0.9 and exact / len(words) >= 0.75
    assert "2026" in result["text"] and "15" in result["text"]
    assert not any(temp.iterdir())                                   # the work folder is removed even on success
