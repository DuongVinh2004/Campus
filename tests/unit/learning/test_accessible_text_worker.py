"""Synthetic candidate geometry, provenance, access boundaries and size limits."""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from campus247_worker.learning.accessible_text import (
    LearningOcrPipeline,
    OcrCandidateError,
    OcrPageArtifacts,
    OcrSource,
    PageGeometry,
    build_page_candidate,
    native_is_usable,
)

WORKSPACE = Path(__file__).resolve(strict=True).parents[3]
HEADER = b"level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"


def native(*lines, width=100, height=200):
    content = "".join(f'<line xMin="{x}" yMin="{y}" xMax="{x + w}" yMax="{y + h}">'
                      f'<word>{text}</word></line>' for text, x, y, w, h in lines)
    return f'<html xmlns="urn:xhtml"><body><doc><page width="{width}" height="{height}">{content}</page></doc></body></html>'.encode()


def raster(*lines):
    return HEADER + "".join(
        f"5\t1\t1\t1\t{index}\t1\t{x}\t{y}\t{w}\t{h}\t{confidence}\t{text}\n"
        for index, (text, x, y, w, h, confidence) in enumerate(lines, 1)
    ).encode()


def source(path: Path, body=b"%PDF-synthetic-test"):
    return OcrSource(path, hashlib.sha256(body).hexdigest(), len(body), 2, "version", "rendition")


class FakeRunner:
    network_disabled = True
    resource_limits_enforced = True

    def __init__(self, artifacts):
        self.profile = {"fake": True}
        self.artifacts = artifacts
        self.scopes = []

    async def process(self, value, page, scope, language):
        self.scopes.append(scope)
        assert not any(scope.iterdir())
        return self.artifacts


def test_native_and_scan_candidates_do_not_auto_publish(tmp_path):
    assert tmp_path.is_relative_to(WORKSPACE)
    clean = native(("Tiếng Việt có dấu", 10, 20, 65, 10))
    assert native_is_usable(clean)
    assert not native_is_usable(native(("1", 20, 20, 20, 10)))
    base = source(tmp_path / "source.pdf")
    result = build_page_candidate(base, 1, "a" * 64, OcrPageArtifacts(PageGeometry(100, 200, 0), clean))
    assert json.loads(result.to_bytes()) == result.payload
    assert hashlib.sha256(result.to_bytes()).hexdigest() == result.sha256
    assert result.payload["raster_sha256"] is None and result.payload["status"] == "NEEDS_REVIEW"
    [block] = result.payload["blocks"]
    assert block["text"] == "Tiếng Việt có dấu"
    assert block["provenance"] == "NATIVE" and block["needs_review"] is True
    assert block["anchor"] == pytest.approx({"x": .1, "y": .1, "width": .65, "height": .05})


def test_mixed_page_preserves_native_and_flags_high_risk_ocr(tmp_path):
    artifacts = OcrPageArtifacts(
        PageGeometry(100, 200, 0),
        native(("Ghi chú gốc", 10, 10, 48, 10)),
        raster(("Ghi chú OCR trùng", 10, 10, 48, 10, 99), ("v = −3 m/s", 15, 35, 50, 10, 61),
               ("12,5 2,0 kg", 16, 60, 51, 12, 88)),
        100, 200, "a" * 64,
    )
    result = build_page_candidate(source(tmp_path / "source.pdf"), 1, "b" * 64, artifacts)
    first, formula, table = result.payload["blocks"]
    assert first["text"] == "Ghi chú gốc" and first["provenance"] == "NATIVE"
    assert formula["text"] == "v = −3 m/s" and formula["provenance"] == "OCR"
    assert {"LOW_CONFIDENCE", "POSSIBLE_FORMULA"}.issubset(formula["review_reasons"])
    assert "POSSIBLE_TABLE" in table["review_reasons"]
    assert all(block["needs_review"] for block in (first, formula, table))


def test_rotation_maps_display_raster_back_to_original_crop(tmp_path):
    artifacts = OcrPageArtifacts(PageGeometry(100, 200, 90), native(),
                                 raster(("Phép đo", 30, 20, 60, 10, 90)), 200, 100, "a" * 64)
    [block] = build_page_candidate(source(tmp_path / "source.pdf"), 2, "b" * 64, artifacts).payload["blocks"]
    assert block["id"] == "p2-b1"
    assert block["anchor"] == pytest.approx({"x": .2, "y": .55, "width": .1, "height": .3})


def test_rotated_poppler_bbox_has_unrotated_size_and_display_coordinates(tmp_path):
    raw = native(("Synthetic native text", 475.102, 40, 12.95, 241.99), width=470, height=586)
    artifacts = OcrPageArtifacts(PageGeometry(470, 586, 90), raw)
    [block] = build_page_candidate(source(tmp_path / "source.pdf"), 1, "b" * 64, artifacts).payload["blocks"]
    assert block["provenance"] == "NATIVE"
    assert block["anchor"] == pytest.approx({"x": 40 / 470, "y": 1 - 488.052 / 586,
                                             "width": 241.99 / 470, "height": 12.95 / 586})


@pytest.mark.parametrize(("artifacts", "code"), [
    (OcrPageArtifacts(PageGeometry(100, 200, 0), b"<!DOCTYPE html [<!ENTITY a 'bad'>]><html/>"), "OCR_NATIVE_RESULT_INVALID"),
    (OcrPageArtifacts(PageGeometry(100, 200, 0), native(width=200, height=100)), "OCR_PAGE_GEOMETRY_MISMATCH"),
    (OcrPageArtifacts(PageGeometry(100, 200, 0), native(("Synthetic native text", float("nan"), 0, 20, 10))),
     "OCR_BLOCK_GEOMETRY_INVALID"),
    (OcrPageArtifacts(PageGeometry(100, 200, 0), native(), raster(("hỏng", 99, 0, 2, 4, 90)), 100, 200, "a" * 64),
     "OCR_RASTER_RESULT_INVALID"),
    (OcrPageArtifacts(PageGeometry(100, 200, 0), native(), HEADER, 3000, 6000, "a" * 64),
     "OCR_RASTER_RESULT_INVALID"),
])
def test_malformed_parser_artifact_fails_closed(tmp_path, artifacts, code):
    with pytest.raises(OcrCandidateError, match=code):
        build_page_candidate(source(tmp_path / "source.pdf"), 1, "b" * 64, artifacts)


def test_worker_refuses_untrusted_runner_wrong_hash_and_page(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    fake = FakeRunner(OcrPageArtifacts(PageGeometry(100, 200, 0), native()))
    fake.network_disabled = False
    with pytest.raises(OcrCandidateError, match="OCR_SANDBOX_UNVERIFIED"):
        LearningOcrPipeline(workspace=WORKSPACE, work_root=work, runner=fake)
    fake.network_disabled = True
    pipeline = LearningOcrPipeline(workspace=WORKSPACE, work_root=work, runner=fake)
    path = tmp_path / "source.pdf"
    with path.open("xb") as stream:
        stream.write(b"%PDF-synthetic-test")
    with pytest.raises(OcrCandidateError, match="OCR_SOURCE_INVALID"):
        asyncio.run(pipeline.process_page(source(path), 3))
    with pytest.raises(OcrCandidateError, match="OCR_SOURCE_CHANGED"):
        asyncio.run(pipeline.process_page(source(path, b"%PDF-synthetic-FAIL"), 1))
    assert not fake.scopes
    page = asyncio.run(pipeline.process_page(source(path), 1))
    assert page.payload["blocks"] == []
    assert page.payload["profile_sha256"] == pipeline.profile_sha256
    assert path.read_bytes() == b"%PDF-synthetic-test"
