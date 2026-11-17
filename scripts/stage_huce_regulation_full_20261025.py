"""Prepare complete numbered clauses with exact multi-page witnesses; stage explicitly."""
import argparse
import asyncio
import copy
import re
from datetime import UTC, datetime

import complete_huce_corpus as corpus
from continue_huce_completion_20261025 import CORPUS, OLD, OUT, REGULATION, ROOT, read, save, sha
from campus247.application.knowledge.source_snapshot import validate_snapshot


def prepare():
    transcript_path = OUT / "regulation-reviewed-pages-01.json"
    transcript = read(transcript_path)
    assert transcript["reviewed_pages"] == list(range(2, 27)) and transcript["complete_pdf_body"]
    plan = read(CORPUS / "candidate-plan-08.json")
    entry = next(e for e in plan["sources"] if e["source_id"] == REGULATION)
    candidate = read(ROOT / entry["candidate"])
    assert sha((ROOT / entry["candidate"]).read_bytes()) == entry["candidate_sha256"]
    assert candidate["original_sha256"] == transcript["original_sha256"]
    candidate = copy.deepcopy(candidate)
    candidate["previous_version_id"] = next(e for e in read(OLD / "source-status-final-01.json")["sources"]
        if e["source_id"] == REGULATION)["serving_version"]
    document, ranges = "", []
    for page in transcript["pages"]:
        assert sha(page["text"].encode()) == page["text_sha256"]
        assert sha((ROOT / page["image"]).read_bytes()) == page["image_sha256"]
        ranges.append((len(document), len(document)+len(page["text"]), page))
        document += page["text"] + "\n"

    def spans(start, end):
        result = []
        for lo, hi, pg in ranges:
            a, b = max(start, lo), min(end, hi)
            if a < b:
                text = pg["text"][a-lo:b-lo]
                result.append({"page": pg["page"], "char_start": a-lo, "char_end": b-lo,
                    "text": text, "text_sha256": sha(text.encode()), "image_sha256": pg["image_sha256"]})
        return result

    # Headings may wrap, but only article 15 wraps before the following blank line.
    starts = list(re.finditer(r"(?m)^Điều (\d+)\. [^\n]+", document))
    assert [int(m[1]) for m in starts] == list(range(1, 22))
    blocks = [candidate["extracted"]["blocks"][0]]  # retained reviewed signed decision
    units = []
    for i, match in enumerate(starts):
        end = starts[i+1].start() if i+1 < len(starts) else len(document)
        chapter = re.search(r"(?m)^Chương [IVX]+", document[match.end():end])
        if chapter:
            end = match.end() + chapter.start()
        heading_end = document.find("\n\n", match.start(), end)
        if heading_end == -1:
            heading_end = match.end()
        heading = document[match.start():heading_end].strip()
        numbered = list(re.finditer(r"(?m)^(\d+)\. ", document[heading_end:end]))
        boundaries = [(heading_end+m.start(), m[1]) for m in numbered] or [(heading_end, None)]
        # Article 21 also has an unnumbered introduction.
        if document[heading_end:boundaries[0][0]].strip():
            boundaries.insert(0, (heading_end, None))
        for j, (start, number) in enumerate(boundaries):
            stop = boundaries[j+1][0] if j+1 < len(boundaries) else end
            body = document[start:stop].strip()
            if not body:
                continue
            actual_start = start + len(document[start:stop]) - len(document[start:stop].lstrip())
            actual_end = stop - len(document[start:stop]) + len(document[start:stop].rstrip())
            witness = spans(actual_start, actual_end)
            text = heading + "\n" + body
            section = f"Quy chế 1486 — Điều {match[1]}" + (f", khoản {number}" if number else "")
            section += " — PDF " + "–".join(str(n) for n in sorted({s["page"] for s in witness}))
            block = {"block_id": str(len(blocks)), "page": witness[0]["page"],
                "page_end": witness[-1]["page"], "text": text, "section": section,
                "heading_spans": spans(match.start(), heading_end), "body_spans": witness,
                "join_rule": "Exact heading + newline + exact body; original page separators are newlines"}
            blocks.append(block); units.append(block)
    candidate["extracted"]["blocks"] = blocks
    candidate["extracted"]["review_witness"] = {"extractor": transcript["method"],
        "transcript": str(transcript_path.relative_to(ROOT)), "transcript_sha256": sha(transcript_path.read_bytes()),
        "reviewed_pdf_body_pages": list(range(2, 27)), "articles": list(range(1, 22)),
        "decision_page_preserved": True, "referenced_appendices_present": False,
        "source_anomalies_preserved": transcript["source_anomalies_preserved"]}
    candidate["applicability"]["reviewed_at"] = datetime.now(UTC).isoformat()
    candidate["applicability"]["limitations"] = transcript["limitations"]
    selectors = []
    for block in blocks:
        # Complete clauses remain intact; indexer makes smaller embedding spans
        # while retaining the complete source parent for conditions/exceptions.
        assert len(block["text"].encode()) <= 10000, (block["section"], len(block["text"].encode()))
        selectors.append({"block_id": block["block_id"], "page": block["page"],
            "page_end": block.get("page_end", block["page"]), "char_start": 0,
            "char_end": len(block["text"]), "text": block["text"],
            "text_sha256": sha(block["text"].encode()), "section": block.get("section", "Quyết định 1486 — PDF 1")})
    candidate["pages"] = selectors
    validate_snapshot(candidate, candidate["extracted"], original_sha256=candidate["original_sha256"],
        effective_from=datetime.fromisoformat(candidate["applicability"]["legal_effective_from"]))
    dest = OUT / "regulation-candidate-01.json"
    save(dest, candidate)
    entry.update(candidate=str(dest.relative_to(ROOT)), candidate_sha256=sha(dest.read_bytes()), parents=len(selectors))
    save(CORPUS / "candidate-plan-09.json", plan)
    save(OUT / "regulation-clause-witness-01.json", {"units": units, "unit_count": len(units),
        "body_pages": 25, "candidate_sha256": entry["candidate_sha256"], "activated": False})
    print({"complete_clause_units": len(units), "all_articles": 21, "body_pages": 25})


def range_plan():
    plan = read(CORPUS / "candidate-plan-09.json")
    entry = next(e for e in plan["sources"] if e["source_id"] == REGULATION)
    candidate = read(ROOT / entry["candidate"])
    assert sha((ROOT / entry["candidate"]).read_bytes()) == entry["candidate_sha256"]
    candidate["extracted"]["review_witness"]["page_range_contract"] = "Both page_start and page_end retained in knowledge_chunk; exact per-page spans in extraction"
    target = OUT / "regulation-candidate-02.json"
    save(target, candidate)
    entry.update(candidate=str(target.relative_to(ROOT)), candidate_sha256=sha(target.read_bytes()))
    save(CORPUS / "candidate-plan-10.json", plan)
    print({"new_plan": "10", "old_candidate_and_release_preserved": True})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "range-plan", "backup", "stage", "build"])
    parser.add_argument("--plan", choices=["09", "10"], default="10")
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare()
    elif args.mode == "range-plan":
        range_plan()
    elif args.mode == "backup":
        from backup_huce_evidence_20261025 import backup
        asyncio.run(backup("pre-stage-20261025-02"))
    elif args.mode == "stage":
        asyncio.run(corpus.stage(plan_name=f"candidate-plan-{args.plan}.json"))
    else:
        asyncio.run(corpus.review_and_build(True, f"candidate-plan-{args.plan}.json"))
