"""Render acquired official regulation pages for local OCR and visual checking."""
import sys
from pathlib import Path
from acquire_huce_public_knowledge import DEST, checked

sys.path.append(str(Path(sys.base_prefix) / "Lib/site-packages"))
import pypdfium2 as pdfium

document = pdfium.PdfDocument(str(DEST / "training-regulations.pdf"))
output = checked(DEST / "regulation-pages")
output.mkdir(exist_ok=True)
for number in range(len(document)):
    target = checked(output / f"page-{number + 1:02}.png")
    if target.exists():
        continue
    page = document[number]
    bitmap = page.render(scale=2.5)
    with target.open("xb") as stream:
        bitmap.to_pil().save(stream, format="PNG")
    bitmap.close(); page.close()
count = len(document)
document.close()
print("rendered", count)
