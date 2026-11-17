"""Public publisher witnesses, redacted integration discovery and original geometry."""
import argparse
import io
import json
import os
import re
import sys
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from continue_huce_completion_20261025 import CORPUS, OLD, OUT, ROOT, checked, read, save, sha


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []; self.current = None; self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.current = dict(attrs).get("href"); self.parts = []

    def handle_data(self, data):
        if self.current is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.links.append({"href": self.current, "text": " ".join("".join(self.parts).split())})
            self.current = None


def publishers():
    import httpx
    urls = ["https://huce.edu.vn/khung-chuong-trinh-dao-tao-chinh-quy",
        "https://fit.huce.edu.vn/chuong-trinh-dao-tao",
        "https://www.huce.edu.vn/khoa-cong-nghe-thong-tin",
        "https://www.huce.edu.vn/sinh-vien-khoa-1-chuong-trinh-lkdt-chuyen-tiep-giai-doan-2-sang-dai-hoc-mississippi-hoa-ky-",
        "https://dtqt.huce.edu.vn/tuyen-sinh-dai-hoc"]
    unresolved = [r for r in read(OLD / "remaining-evidence-worklist-01.json")["sources"]
        if r["category"] == "SOURCE_SCOPE_UNRESOLVED"]
    records = []
    with httpx.Client(trust_env=False, timeout=40, follow_redirects=True) as client:
        for i, url in enumerate(urls, 1):
            response = client.get(url); response.raise_for_status()
            host = urlsplit(str(response.url)).hostname
            assert host == "huce.edu.vn" or host.endswith(".huce.edu.vn")
            target = checked(OUT / f"publisher-supplement-{i:02}.html")
            with target.open("xb") as stream:
                stream.write(response.content)
            parser = Links(); parser.feed(response.text)
            links = [{**link, "href": urljoin(str(response.url), link["href"])} for link in parser.links]
            matches = []
            for row in unresolved:
                identifier = re.search(r"/d/([^/]+)", row["uri"])[1]
                exact = [link for link in links if identifier in link["href"]]
                matches.append({"source_id": row["source_id"], "drive_id": identifier, "exact_links": exact,
                    "specific_cohort_proven": False,
                    "reason": "A link or programme description without explicit cohort-to-this-original binding does not supply cohort authority"})
            records.append({"uri": url, "final_uri": str(response.url), "status": response.status_code,
                "file": str(target.relative_to(ROOT)), "sha256": sha(response.content),
                "exact_original_matches": matches, "links": links})
    save(OUT / "supplemental-publishers-01.json", {"at": datetime.now(UTC), "pages": records,
        "unresolved_sources": unresolved, "specific_cohorts_asserted": [],
        "rejected_inferences": ["Enrolment event K70 does not bind any particular PDF revision",
            "Programme inception year and first international intake do not identify this curriculum's cohort",
            "FIT multimedia link text partly points to the network PDF; do not transfer applicability across links"]})
    print({"official_pages_retained": len(records), "unresolved_specific_cohorts": len(unresolved)})


def integration():
    pattern = re.compile(r"(^|_)(SSO|OIDC|OAUTH|SAML|HUCE|SIS|ACADEMIC|ENTRA|AZURE|MSAL)(_|$)", re.I)
    paths = [ROOT / name for name in (".env", ".env.example", "apps/web/.env.local")]
    files = []
    for path in paths:
        keys = []
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.lstrip().startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    if pattern.search(key.strip()):
                        keys.append({"name": key.strip(), "nonempty": bool(value.strip())})
        files.append({"file": str(path.relative_to(ROOT)), "exists": path.is_file(), "integration_keys": keys})
    process = [{"name": key, "nonempty": bool(value)} for key, value in os.environ.items() if pattern.search(key)]
    code = ["services/api/src/campus247/bootstrap/settings.py", "services/api/src/campus247/bootstrap/app.py",
        "services/api/src/campus247/ports/identity.py", "services/api/src/campus247/ports/schedule.py",
        "scripts/knowledge_platform.py"]
    save(OUT / "integration-preflight-01.json", {"at": datetime.now(UTC), "config_files": files,
        "process_integration_keys": process, "inspected_code_sha256": {p: sha((ROOT/p).read_bytes()) for p in code},
        "runtime_identity": "LocalOwnerIdentityAdapter, task-owned huce-local-public tenant",
        "academic_adapter": "SyntheticScheduleAdapter; no HUCE adapter implemented or endpoint declared",
        "real_integration_attempted": False, "real_data_access_granted": False,
        "missing_evidence": ["HUCE-issued identity protocol and issuer metadata", "Registered client and redirect URI",
            "HUCE API specification, base URL and permitted routes", "Approved scopes, audience and subject mapping",
            "Explicit data-access grant and authorized environment/test principal"],
        "values_or_credentials_exported": False,
        "claim_limit": "Absence in these known workspace/process locations; no claim about credentials held outside this workspace"})
    print({"integration_config_keys": sum(len(f["integration_keys"]) for f in files) + len(process),
        "real_huce_integration": False, "report": str(OUT / "integration-preflight-01.json")})


def geometry():
    import pdfplumber
    import pypdfium2 as pdfium
    remaining = read(OLD / "remaining-evidence-worklist-01.json")["sources"]
    plan = {r["source_id"]: r for r in read(CORPUS / "candidate-plan-10.json")["sources"]}
    folder = checked(OUT / "original-geometry-01"); folder.mkdir(exist_ok=True)
    records = []
    for index, row in enumerate(remaining, 1):
        entry = plan[row["source_id"]]
        candidate = read(ROOT / entry["candidate"])
        checksum = candidate["original_sha256"]
        original = ROOT / "data/huce-discovery-20261020/objects" / checksum
        if candidate.get("replacement_original"):
            original = ROOT / candidate["replacement_original"]["file"]
        if not original.is_file():
            info = read(CORPUS / "original-extraction-03" / (checksum + ".json"))
            original = ROOT / "infra/local/knowledge-platform-20261023/artifacts" / info["original_object_key"]
        raw = checked(original).read_bytes(); assert sha(raw) == checksum
        if not raw.startswith(b"%PDF"):
            records.append({**row, "original_sha256": checksum, "status": "NON_PDF_ORIGINAL_REQUIRES_SEPARATE_REVIEW"})
            continue
        dest = checked(folder / row["source_id"]); dest.mkdir(exist_ok=True)
        pages = []
        with pdfplumber.open(io.BytesIO(raw)) as pdf, pdfium.PdfDocument(raw) as renderer:
            for n, page in enumerate(pdf.pages, 1):
                tables = []
                for tindex, table in enumerate(page.find_tables()):
                    values = table.extract()
                    table_rows = []
                    for rindex, trow in enumerate(table.rows):
                        cells = []
                        for cindex, bbox in enumerate(trow.cells):
                            if bbox is None:
                                continue
                            value = values[rindex][cindex]
                            cells.append({"row": rindex, "column": cindex, "bbox": list(bbox), "text": value,
                                "text_sha256": sha((value or "").encode())})
                        table_rows.append(cells)
                    tables.append({"index": tindex, "bbox": list(table.bbox), "rows": table_rows})
                # Every line/curve/rectangle retains its original object index,
                # colour, dash and path. No course relationship inferred here.
                shapes = [{"object_index": j, **{k: obj.get(k) for k in ("object_type", "x0", "top", "x1", "bottom",
                    "pts", "path", "stroke", "fill", "linewidth", "dash", "stroking_color", "non_stroking_color")}}
                    for j, obj in enumerate(page.lines + page.rects + page.curves)]
                image_path = checked(dest / f"page-{n:03}.png")
                rendered = renderer[n-1].render(scale=min(3, 2600/max(page.width, page.height))).to_pil()
                encoded = io.BytesIO(); rendered.save(encoded, format="PNG")
                if image_path.exists():
                    assert sha(image_path.read_bytes()) == sha(encoded.getvalue()), "Retained image differs from original render"
                else:
                    with image_path.open("xb") as stream:
                        stream.write(encoded.getvalue())
                evidence = {"page": n, "width": page.width, "height": page.height,
                    "text": page.extract_text() or "", "tables": tables, "shapes": shapes,
                    "image": str(image_path.relative_to(ROOT)), "image_sha256": sha(image_path.read_bytes()),
                    "review_state": "UNREVIEWED_ORIGINAL_GEOMETRY", "relations_admitted": False,
                    "image_objects": len(page.images)}
                page_path = checked(dest / f"page-{n:03}.json")
                if page_path.exists():
                    assert read(page_path) == json.loads(json.dumps(evidence)), "Retained geometry changed"
                else:
                    save(page_path, evidence)
                pages.append({"page": n, "evidence": str(page_path.relative_to(ROOT)), "sha256": sha(page_path.read_bytes()),
                    "image": evidence["image"], "image_sha256": evidence["image_sha256"],
                    "cells": sum(len(r) for t in tables for r in t["rows"]), "vector_shapes": len(shapes)})
        records.append({**row, "original": str(original.relative_to(ROOT)), "original_sha256": checksum,
            "candidate_sha256": entry["candidate_sha256"], "kind": candidate["applicability"]["kind"],
            "pages": pages, "status": "ORIGINAL_GEOMETRY_RETAINED_NOT_REVIEWED"})
        print(json.dumps({"processed": index, "source_id": row["source_id"], "pages": len(pages)}), flush=True)
    save(OUT / "original-geometry-manifest-01.json", {"sources": records, "source_count": len(records),
        "pages": sum(len(r.get("pages", [])) for r in records), "all_content_complete": False,
        "qualification": "Geometry and table candidates are inspection aids; none are automatically admitted"})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(); parser.add_argument("mode", choices=["publishers", "integration", "geometry"])
    mode = parser.parse_args().mode
    {"publishers": publishers, "integration": integration, "geometry": geometry}[mode]()
