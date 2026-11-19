"""PDF coverage and source-preview binding with synthetic in-memory PDF inputs."""
import asyncio
import io
import json
import os
from dataclasses import replace

import pytest
from starlette.datastructures import UploadFile, Headers

from campus247.application.knowledge.document_identity import DraftIntakeInput
from campus247.application.knowledge.platform_models import PlatformError
from campus247_worker.knowledge import KnowledgeIngestionWorker
from .test_draft_postgres import setup, NoModel
from .conftest import ROOT

pytestmark = pytest.mark.skipif(not os.environ.get("KNOWLEDGE_AUTOMATION_REHEARSAL"), reason="Fresh retained PostgreSQL rehearsal required")


def synthetic_pdf(kind):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, NumberObject, DecodedStreamObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=400)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    resources = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    commands = b"BT /F1 12 Tf 20 380 Td (Synthetic long native header for coverage verification.) Tj ET\n"
    if kind == "image":
        image = DecodedStreamObject()
        image.set_data(b"\xff" * (100*100*3))
        image.update({NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(100), NameObject("/Height"): NumberObject(100),
            NameObject("/ColorSpace"): NameObject("/DeviceRGB"), NameObject("/BitsPerComponent"): NumberObject(8)})
        resources[NameObject("/XObject")] = DictionaryObject({NameObject("/Im0"): writer._add_object(image)})
        commands += b"q 250 0 0 250 20 20 cm /Im0 Do Q\n"
    elif kind == "table":
        commands += b"20 100 240 200 re S 140 100 m 140 300 l S 20 200 m 260 200 l S\n"
    elif kind == "diagram":
        commands += b"40 100 m 240 300 l S 240 300 m 230 280 l S 240 300 m 220 290 l S\n"
    page[NameObject("/Resources")] = resources
    content = DecodedStreamObject(); content.set_data(commands)
    page[NameObject("/Contents")] = writer._add_object(content)
    out = io.BytesIO(); writer.write(out)
    return out.getvalue()


@pytest.mark.parametrize("kind,route,needs_review", [("text", "NATIVE_TEXT", False),
    ("image", "RASTER_OR_MIXED", True), ("table", "NATIVE_TABLE", True), ("diagram", "NATIVE_GRAPHICS", True)])
def test_native_header_does_not_hide_image_table_or_diagram(monkeypatch, retained_directory, kind, route, needs_review):
    async def run():
        pool, repo, platform, actor, intake, _ = await setup(retained_directory)
        worker = KnowledgeIngestionWorker(repo, platform.storage, NoModel(), owner="layout-test", low_watermark=0,
            parser_python=ROOT / ".venv/Scripts/python.exe")
        try:
            accepted = await intake.accept(actor, UploadFile(io.BytesIO(synthetic_pdf(kind)), filename="synthetic-"+kind+".pdf",
                headers=Headers({"content-type": "application/pdf"})), DraftIntakeInput(), "layout")
            await worker.run_once()
            item = (await intake.list(actor))["items"][0]
            assert item["state"] == "NEEDS_INFORMATION", item
            async with pool.acquire() as conn:
                step = await repo.checkpoint({"id": accepted["job_id"]}, "EXTRACT", accepted["original_sha256"], worker.parse_config_hash)
                saved = await conn.fetchrow("SELECT * FROM knowledge_artifact WHERE id=$1", step["artifact_id"])
                result = json.loads(platform.storage.read(saved))
            assert result["pages"][0]["layout"]["route"] == route
            assert bool(result["issues"]) == needs_review
            if needs_review:
                image = await intake.preview(actor, accepted["intake_id"], 1)
                assert image.startswith(b"\x89PNG\r\n\x1a\n")
                assert item["issues"][0]["evidence"]["preview_pages"] == [1]
                with pytest.raises(PlatformError, match="KNOWLEDGE_FORBIDDEN"):
                    await intake.preview(replace(actor, tenant_id="other"), accepted["intake_id"], 1)
            assert result["parser_identity"] == worker.parser_identity
            evidence = await intake.evidence(actor, accepted["intake_id"])
            assert evidence["original_sha256"] == accepted["original_sha256"]
            assert evidence["tenant_id"] == repo.tenant and evidence["admission_granted"] is False
            assert evidence["units"]
            if kind == "image":
                assert any(unit["kind"] == "IMAGE_REGION" for unit in evidence["units"])
            with pytest.raises(PlatformError, match="KNOWLEDGE_FORBIDDEN"):
                await intake.evidence(replace(actor, tenant_id="other"), accepted["intake_id"])
        finally:
            await pool.close()
    asyncio.run(run())
