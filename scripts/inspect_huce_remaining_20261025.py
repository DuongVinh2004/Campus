"""Retain source-bound inspection material; no database or serving mutation."""
import hashlib
import io
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "infra/local/huce-evidence-20261025-01"
OLD = ROOT / "infra/local/huce-corpus-completion-20261024-01"


def checked(path):
    path = path.resolve()
    if not path.is_relative_to(ROOT.resolve()) or path == ROOT.resolve():
        raise ValueError("Exact workspace child required")
    return path


def read(path):
    return json.loads(checked(path).read_text(encoding="utf-8"))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    with checked(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def main():
    status = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True,
        encoding="utf-8", check=True)
    checked(OUT).mkdir(exist_ok=True)
    if not (OUT / "preflight-01.json").exists():
        save(OUT / "preflight-01.json", {"at": datetime.now(UTC).isoformat(),
            "root": str(ROOT.resolve()), "status": status.stdout, "warnings": status.stderr,
            "scope": "new evidence files only; originals, backups and runtime retained"})
    targets = {r["source_id"]: r for r in read(OLD / "source-status-final-01.json")["sources"]
        if r["category"] == "SOURCE_SCOPE_UNRESOLVED"}
    targets["253eb450-c57a-79a7-84a4-b0d85e12de1c"] = next(r for r in
        read(OLD / "source-status-final-01.json")["sources"]
        if r["source_id"] == "253eb450-c57a-79a7-84a4-b0d85e12de1c")
    records, thumbnails = [], []
    for entry in read(OLD / "candidate-plan-06.json")["sources"]:
        if entry["source_id"] not in targets:
            continue
        candidate = read(ROOT / entry["candidate"])
        original = checked(ROOT / "data/huce-discovery-20261020/objects" / candidate["original_sha256"])
        if not original.is_file():
            extraction = read(OLD / "original-extraction-03" / (candidate["original_sha256"] + ".json"))
            original = checked(ROOT / "infra/local/knowledge-platform-20261023/artifacts" / extraction["original_object_key"])
        raw = original.read_bytes()
        assert sha(raw) == candidate["original_sha256"]
        pages = []
        with pdfium.PdfDocument(raw) as doc:
            for n in range(len(doc)):
                page = doc[n]
                tp = page.get_textpage()
                text = tp.get_text_bounded().replace("\r", "")
                tp.close()
                # Full pages remain separately inspectable, including sparse pages.
                dest = checked(OUT / f"{entry['source_id']}-p{n+1}.png")
                image = page.render(scale=min(2.5, 2600/max(page.get_size()))).to_pil()
                encoded = io.BytesIO()
                image.save(encoded, format="PNG")
                if dest.exists():
                    assert sha(dest.read_bytes()) == sha(encoded.getvalue()), "Retained render changed"
                else:
                    with dest.open("xb") as stream:
                        stream.write(encoded.getvalue())
                if entry["source_id"] != "253eb450-c57a-79a7-84a4-b0d85e12de1c":
                    thumb = image.copy()
                    thumb.thumbnail((700, 480))
                    tile = Image.new("RGB", (720, 520), "white")
                    tile.paste(thumb, (10, 30))
                    ImageDraw.Draw(tile).text((10, 5), f"{entry['source_id'][:8]} page {n+1}", fill="black")
                    thumbnails.append(tile)
                pages.append({"page": n+1, "dimensions": list(page.get_size()), "native_text": text,
                    "cohort_mentions": re.findall(r"(?i)(?:k\s*\d{2}|kh[oó]a\s+\d{2})", text),
                    "image": str(dest.relative_to(ROOT)), "image_sha256": sha(dest.read_bytes())})
                page.close()
        records.append({"source_id": entry["source_id"], "title": entry["title"],
            "uri": entry["uri"], "original": str(original.relative_to(ROOT)),
            "original_sha256": sha(raw), "candidate_sha256": entry["candidate_sha256"],
            "publisher_witness": candidate["extracted"].get("publisher_witness"), "pages": pages,
            "status": "inspection_material_only_not_admitted"})
    for start in range(0, len(thumbnails), 6):
        sheet = Image.new("RGB", (1440, 1560), "#dddddd")
        for n, tile in enumerate(thumbnails[start:start+6]):
            sheet.paste(tile, ((n % 2)*720, (n//2)*520))
        with checked(OUT / f"contact-{start//6+1:02}.png").open("xb") as stream:
            sheet.save(stream, format="PNG")
    save(OUT / "inspection-material-01.json", {"at": datetime.now(UTC).isoformat(), "sources": records,
        "admitted": False, "note": "Extraction is a locator aid; visual review and scope proof still required."})
    print(json.dumps({"sources": len(records), "pages": sum(len(r['pages']) for r in records),
        "out": str(OUT)}))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
