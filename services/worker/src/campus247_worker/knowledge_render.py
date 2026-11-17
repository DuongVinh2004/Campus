"""Poppler preview adapter, separate from the read-only Python parser.

The executable only receives a hash-checked local PDF and a new scoped output.
All temp/font cache/output files are retained inside the workspace namespace.
"""
import asyncio
import os
import shutil
import sys
import time
from pathlib import Path
from uuid import uuid4
from xml.etree.ElementTree import Element, SubElement, tostring

from campus247.application.knowledge.platform_models import PlatformError, digest
from campus247.infrastructure.knowledge.storage import checked_path


class PreviewRenderer:
    def __init__(self, storage):
        self.storage = storage
        found = shutil.which("pdftoppm")
        self.executable = Path(found).resolve(strict=True) if found else None
        self.profile = {"adapter": "poppler-page-preview-v1", "scale_to": 2700, "format": "png",
            "binary_sha256": digest(self.executable.read_bytes()) if self.executable else None,
            "font_source": "Windows Fonts; font revisions not independently pinned", "semantics_verified": False}
        self.config_hash = digest(self.profile)

    async def render(self, artifact, page):
        if not self.executable:
            raise PlatformError(503, "PREVIEW_RENDERER_UNAVAILABLE", "Chưa có renderer ảnh đối chiếu.")
        if type(page) is not int or not 1 <= page <= 500 or artifact["media_type"] != "application/pdf":
            raise PlatformError(422, "PREVIEW_PAGE_INVALID", "Trang PDF không hợp lệ.")
        self.storage.read(artifact)
        scope = checked_path(self.storage.root.parent / ("render-"+uuid4().hex), self.storage.workspace)
        scope.mkdir(exist_ok=False)
        output = checked_path(scope / "preview.png", self.storage.workspace)
        prefix = checked_path(scope / "preview", self.storage.workspace)
        config = checked_path(scope / "fonts.conf", self.storage.workspace)
        tree = Element("fontconfig")
        SubElement(tree, "dir").text = str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts")
        SubElement(tree, "cachedir").text = str(checked_path(scope / "font-cache", self.storage.workspace))
        with config.open("xb") as stream:
            stream.write(tostring(tree, encoding="utf-8", xml_declaration=True))
        environment = {key: value for key, value in os.environ.items() if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR"}}
        environment.update(TEMP=str(scope), TMP=str(scope), FONTCONFIG_FILE=str(config), FONTCONFIG_PATH=str(scope), XDG_CACHE_HOME=str(scope))
        started = time.perf_counter()
        child = await asyncio.create_subprocess_exec(str(self.executable), "-q", "-f", str(page), "-l", str(page),
            "-singlefile", "-scale-to", "2700", "-png", str(self.storage.path(artifact["object_key"])), str(prefix),
            cwd=scope, env=environment, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            creationflags=0x08000000 if sys.platform == "win32" else 0)
        try:
            await asyncio.wait_for(child.wait(), 120)
            if child.returncode or not output.is_file() or output.stat().st_size > 8*1024**2:
                raise PlatformError(422, "PREVIEW_RENDER_FAILED", "Chưa tạo được ảnh đối chiếu có giới hạn.")
            self.storage.read(artifact)  # Refuse a source changed during rendering.
            png = output.read_bytes()
            if not png.startswith(b"\x89PNG\r\n\x1a\n"):
                raise PlatformError(409, "PREVIEW_IMAGE_INVALID", "Ảnh đối chiếu không hợp lệ.")
            return self.storage.write_bytes(png, "review-preview", "image/png"), {
                "page": page, "source_sha256": artifact["sha256"], "renderer": self.profile,
                "elapsed_seconds": time.perf_counter()-started, "output_bytes": len(png), "new_model_calls": 0,
                "cpu_seconds": None, "cpu_measurement": "not measured", "review_status": "UNREVIEWED"}
        finally:
            if child.returncode is None:
                child.kill()
                await child.wait()
