"""Render the service and FAQ pages whose tightly spaced text needs OCR."""
import sys
from pathlib import Path
from acquire_huce_public_knowledge import DEST, checked

sys.path.append(str(Path(sys.base_prefix) / "Lib/site-packages"))
import pypdfium2 as pdfium

PAGES = [15, 27, 28, 29, 34, 35, 70, 71, *range(106, 116)]
output = checked(DEST / "handbook-pages")
output.mkdir(exist_ok=True)
with pdfium.PdfDocument(str(DEST / "handbook-2026-2027.pdf")) as document:
    for number in PAGES:
        target = checked(output / f"page-{number:03}.png")
        if target.exists():
            continue
        page = document[number - 1]
        bitmap = page.render(scale=2.5)
        with target.open("xb") as stream:
            bitmap.to_pil().save(stream, format="PNG")
        bitmap.close(); page.close()
print("rendered handbook sections", len(PAGES))
