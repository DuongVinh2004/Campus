"""Prepare six additive replacements from reviewed pages and publication rows."""
import json
from copy import deepcopy
from datetime import UTC, datetime

from complete_huce_corpus import SCOPE, publication_bindings, read, windows
from knowledge_platform import ROOT, checked_path, retain
from campus247.application.knowledge.platform_models import digest
from campus247.application.knowledge.source_snapshot import validate_snapshot

OUT = checked_path(ROOT / "infra/local/huce-evidence-20261025-01", ROOT)
CALENDAR = "c2454951-46ce-7a56-8421-ca4927bf3339"
REGULATION = "253eb450-c57a-79a7-84a4-b0d85e12de1c"
SHARED = {"4b89bce7-4935-713b-8747-f97a0853d726", "8da40ef9-1850-7fa5-878d-86a2eb357674",
    "bc455d2c-2b63-734f-8f60-7796c9635290", "dc43e7f5-466f-7ce3-8fe2-a10a0c809d9b"}


def calendar_blocks(record):
    """Flatten only the four visually checked rows, preserving every week cell."""
    result = []
    for row in record["rows"]:
        lines = ["KẾ HOẠCH GIẢNG DẠY VÀ HỌC TẬP NĂM HỌC 2026-2027", row["cohort_label_verbatim"],
            "Công nghệ thông tin", "Số lớp: " + str(row["class_count"]),
            "Tuần | Ngày BĐ | Ký hiệu | Nền màu theo chú giải"]
        for week in row["weeks"]:
            colour = record["review_dossier"]["reviewed_colour_roles"][week["colour_role"]]["meaning"]
            # Blank stays blank, rather than claiming a teaching/exam schedule.
            if week["colour_role"] == "unmarked":
                colour = ""
            lines.append(f"{week['week']} | {datetime.fromisoformat(week['start_date']).strftime('%d/%m/%Y')} | "
                + f"{week['printed_marker']} | {colour}")
        lines.extend(["Ghi chú và ký hiệu:",
            *[marker + " - " + meaning for marker, meaning in record["review_dossier"]["marker_legend"].items()],
            *[note["source_verbatim"] for note in record["common_notes"]]])
        result.append({"block_id": str(len(result)), "page": 1, "text": "\n".join(lines),
            "source_row_index": row["row_index"], "region_bbox": row["row_bbox"],
            "cohort_bbox": row["cohort_bbox"], "cohorts": [row["cohort"]], "provisional": row["provisional"]})
    return result


def selectors(blocks, title):
    result = []
    for block in blocks:
        for start, end in windows(block["text"]):
            text = block["text"][start:end]
            result.append({"block_id": block["block_id"], "page": block["page"],
                "char_start": start, "char_end": end, "text": text, "text_sha256": digest(text.encode()),
                "section": block.get("section", title + " · trang " + str(block["page"]))
                    + (f" · {block['cohorts'][0]} · hàng {block['source_row_index']}" if "cohorts" in block else ""),
                **({"cohorts": block["cohorts"]} if "cohorts" in block else {})})
    return result


def main():
    from huce_calendar_pipeline import normalize
    plan = read(SCOPE / "candidate-plan-06.json")
    baseline = {r["source_id"]: r for r in read(SCOPE / "source-status-final-01.json")["sources"]}
    publication = read(ROOT / "data/huce-discovery-20261020/curricula-20261020T153323371137Z/manifest.json")
    pubraw = checked_path(ROOT / publication["publication"]["original_file"], ROOT).read_bytes()
    assert digest(pubraw) == publication["publication"]["sha256"]
    current = read(OUT / "publisher-rows-01.json")
    assert digest((OUT / "publisher-20261025-01.html").read_bytes()) == current["sha256"]
    material = {r["source_id"]: r for r in read(OUT / "inspection-material-01.json")["sources"]}
    folder = checked_path(OUT / "candidates-01", ROOT)
    folder.mkdir(exist_ok=False)
    changed, dispositions = [], []
    for entry in plan["sources"]:
        identifier = entry["source_id"]
        if identifier not in SHARED | {CALENDAR, REGULATION}:
            if baseline[identifier]["category"] == "SOURCE_SCOPE_UNRESOLVED":
                dispositions.append({"source_id": identifier, "category": "SOURCE_SCOPE_UNRESOLVED",
                    "evidence": str((OUT / "inspection-material-01.json").relative_to(ROOT)),
                    "reason": "No printed cohort on inspected original pages; exact download appears only in generic K70-and-earlier publication table. No specific cohort asserted."})
            continue
        candidate = deepcopy(read(ROOT / entry["candidate"]))
        assert digest((ROOT / entry["candidate"]).read_bytes()) == entry["candidate_sha256"]
        candidate["previous_version_id"] = baseline[identifier]["serving_version"]
        scope = candidate["applicability"]
        scope["reviewed_at"] = datetime.now(UTC).isoformat()
        if identifier in SHARED:
            rows = publication_bindings(publication, candidate["original_sha256"], entry["uri"])
            k71 = [r for r in rows if r["table_index"] == 0 and r["scope"] == "K71"]
            assert len(k71) == 1
            drive_id = k71[0]["drive_id"]
            current_rows = [r for r in current["tables"][0]["rows"]
                if any(drive_id in link for link in r["links"])]
            assert len(current_rows) == 1 and current_rows[0]["cells"] == k71[0]["row_cells"]
            scope["cohorts"] = ["K71"]
            scope["limitations"] = [r for r in scope.get("limitations", [])
                if r not in {"Printed 2025; do not assign to a cohort unless the source states it",
                    "Printed 2025; no cohort inferred from the publication's mixed links"}]
            scope["limitations"].append("K71 established by the exact official publication table row; generic earlier-cohort row does not prove K70 or any earlier cohort.")
            candidate["extracted"]["publisher_witness"] = {"uri": publication["publication"]["url"],
                "sha256": publication["publication"]["sha256"], "rows": rows,
                "current_publication_sha256": current["sha256"], "current_k71_rows": current_rows,
                "download_binding": {"drive_id": drive_id, "original_sha256": candidate["original_sha256"]}}
            dispositions.append({"source_id": identifier, "category": "PARTIAL_SOURCE_TEXT",
                "cohorts": ["K71"], "proof": k71, "not_proven": "K70 and individual earlier cohorts; semester cells and arrows"})
        elif identifier == CALENDAR:
            dossier = read(ROOT / "data/huce-document-pipeline/calendar-cntt-review-bound-20261022-35.json")
            record = normalize(dossier)
            retain(OUT / "calendar-revalidated-01.json", record)
            blocks = calendar_blocks(record)
            # Every selected block is bound to exactly one original merged cohort label.
            scope.update(cohorts=[r["cohort"] for r in record["rows"]], cohort_partitioned=True,
                mixed_cohort_table=False, academic_years=["2026-2027"], requires_academic_year=True,
                programme_codes=[], relations_verified=False,
                limitations=record["limitations"] + ["Only printed week cells and colour legend; no inferred individual timetable or unreviewed major rows."])
            candidate["extracted"] = {"original_sha256": candidate["original_sha256"], "blocks": blocks,
                "review_witness": {"extractor": "reviewed-table-cell-transcription-v1", "dossier": dossier,
                    "revalidated_record": str((OUT / "calendar-revalidated-01.json").relative_to(ROOT)),
                    "revalidated_sha256": digest((OUT / "calendar-revalidated-01.json").read_bytes()),
                    "all_208_cells_reconciled": True, "complete_document": False}}
            candidate["pages"] = selectors(blocks, entry["title"])
            dispositions.append({"source_id": identifier, "category": "PARTIAL_SOURCE_TEXT", "rows": 4,
                "week_cells": 208, "not_proven": "Other-major rows, individual timetable, semester-specific query support"})
        else:
            transcript = read(OUT / "regulation-selected-pages-01.json")
            assert transcript["original_sha256"] == candidate["original_sha256"]
            blocks = candidate["extracted"]["blocks"]
            for page in transcript["pages"]:
                source_image = material[identifier]["pages"][page["page"]-1]
                assert digest((ROOT / source_image["image"]).read_bytes()) == source_image["image_sha256"]
                blocks.append({"block_id": str(len(blocks)), **page, "image": source_image["image"],
                    "image_sha256": source_image["image_sha256"]})
            candidate["extracted"]["review_witness"] = {"extractor": transcript["method"],
                "original_decision_witness": candidate["extracted"]["review_witness"],
                "transcript_sha256": digest((OUT / "regulation-selected-pages-01.json").read_bytes()),
                "images": [{k: b[k] for k in ("page", "image", "image_sha256")} for b in blocks[1:]],
                "complete_document": False, "limitations": transcript["limitations"]}
            scope["limitations"] = transcript["limitations"]
            candidate["pages"] = selectors(blocks, entry["title"])
            dispositions.append({"source_id": identifier, "category": "PARTIAL_SOURCE_TEXT", "new_pdf_pages": [2, 3, 4, 5],
                "not_proven": transcript["limitations"]})
        validate_snapshot(candidate, candidate["extracted"], original_sha256=candidate["original_sha256"],
            effective_from=datetime.fromisoformat(scope.get("legal_effective_from") or scope["reviewed_at"]))
        target = checked_path(folder / (identifier + ".json"), ROOT)
        retain(target, candidate)
        entry.update(candidate=str(target.relative_to(ROOT)), candidate_sha256=digest(target.read_bytes()),
            cohorts=scope["cohorts"], parents=len(candidate["pages"]))
        changed.append(identifier)
    assert len(changed) == 6 and len(dispositions) == 13
    retain(SCOPE / "candidate-plan-07.json", plan)
    retain(OUT / "scope-review-01.json", {"changed_sources": changed, "dispositions": dispositions,
        "scope_unresolved_after_evidence": 7, "all_93_limitations_resolved": False,
        "sso_and_personal_academic_api": "not_connected_no_grants_inferred"})
    print(json.dumps({"changed": changed, "unresolved_specific_cohorts": 7, "activation": False}))


if __name__ == "__main__":
    main()
