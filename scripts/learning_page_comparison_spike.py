"""Offline P60 experiment. All input is synthetic and output is suggestions only."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
import re
import statistics
import time
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject, TextStringObject

KINDS = ("UNCHANGED", "MOVED", "EDITED", "ADDED", "REMOVED")
CONFIDENCE = 0.90
MINIMUM_SCORE = 0.68
MINIMUM_MARGIN = 0.10
NOVELTY = 0.34
PageMatch = tuple[str, int | None, int | None]


@dataclass(frozen=True)
class Fingerprint:
    sha256: str
    text: frozenset[str]
    ink: frozenset[int]


def write_pdf(writer):
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def stamp(page, identity, revision):
    page[NameObject("/SyntheticIdentity")] = TextStringObject(identity)
    page[NameObject("/SyntheticRevision")] = TextStringObject(str(revision))


def synthetic_pdf(spec, mode):
    writer = PdfWriter()
    for identity, revision, appearance in spec:
        seed = random.Random(appearance)
        shape = [(x, y, x + seed.randrange(17, 31), y + seed.randrange(10, 20))
                 for x, y in [(seed.randrange(24, 235), seed.randrange(30, 175)) for _ in range(12)]]
        page = writer.add_blank_page(width=280, height=220)
        if mode == "scan":
            image = Image.new("L", (280, 220), 255)
            draw = ImageDraw.Draw(image)
            for box in shape:
                draw.rectangle(box, fill=10)
            if revision:
                draw.rectangle((35, 189, 83, 199), fill=20)
            raw_image = DecodedStreamObject()
            raw_image.set_data(image.tobytes())
            raw_image.update({NameObject(k): NameObject(v) for k, v in (
                ("/Type", "/XObject"), ("/Subtype", "/Image"), ("/ColorSpace", "/DeviceGray"),
            )} | {NameObject(k): NumberObject(v) for k, v in (
                ("/Width", image.width), ("/Height", image.height), ("/BitsPerComponent", 8),
            )})
            resources = {"/XObject": DictionaryObject({NameObject("/Scan"): writer._add_object(raw_image.flate_encode())})}
            operators = "q 280 0 0 220 0 0 cm /Scan Do Q"
        else:
            font = DictionaryObject({NameObject(k): NameObject(v) for k, v in (
                ("/Type", "/Font"), ("/Subtype", "/Type1"), ("/BaseFont", "/Helvetica"),
            )})
            resources = {"/Font": DictionaryObject({NameObject("/F1"): font})}
            title = " ".join(f"{appearance}{ending}" for ending in ("study", "example", "chart", "work", "practice", "review"))
            operators = f"BT /F1 8 Tf 15 202 Td ({title}) Tj ET\n"
            operators += "\n".join(f"{x} {y} {right-x} {bottom-y} re f" for x, y, right, bottom in shape)
            if revision:
                operators += "\nBT /F1 8 Tf 25 15 Td (Updated equation) Tj ET"
        page[NameObject("/Resources")] = DictionaryObject({NameObject(k): v for k, v in resources.items()})
        content = DecodedStreamObject()
        content.set_data(operators.encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(content)
        stamp(page, identity, revision)
    return write_pdf(writer)


def pptx_pdf(rendition, order):
    writer = PdfWriter()
    for index in order:
        page = writer.add_page(rendition.pages[index - 1])
        stamp(page, f"slide-{index}", 0)
    return write_pdf(writer)


def gold(old_pdf, new_pdf, old_spec, new_spec):
    def pages(payload, expected):
        parsed = PdfReader(io.BytesIO(payload), strict=True).pages
        pairs = [(str(page["/SyntheticIdentity"]), int(page["/SyntheticRevision"])) for page in parsed]
        assert pairs == [tuple(item[:2]) for item in expected], "Fixture page order or revision differs from edit manifest"
        assert len(set(identity for identity, _ in pairs)) == len(pairs), "Ambiguous gold identity"
        return {identity: (index, revision) for index, (identity, revision) in enumerate(pairs, 1)}

    before, after = pages(old_pdf, old_spec), pages(new_pdf, new_spec)
    expected = set()
    for identity, (old, revision) in before.items():
        if identity not in after:
            expected.add(("REMOVED", old, None))
            continue
        new, new_revision = after[identity]
        expected.add((match_kind(old, new, revision != new_revision), old, new))
    return expected | {("ADDED", None, new) for identity, (new, _) in after.items() if identity not in before}


def match_kind(old, new, edited):
    if edited:
        return "EDITED"
    return "UNCHANGED" if old == new else "MOVED"


def fingerprints(data):
    result = []
    with pdfium.PdfDocument(data) as document:
        for page in document:
            with closing(page), closing(page.get_textpage()) as text_page, closing(page.render(scale=1, grayscale=True)) as bitmap:
                text = frozenset(re.findall(r"\w+", text_page.get_text_range().casefold()))
                raster = bitmap.to_pil().convert("L")
                digest = hashlib.sha256(f"{raster.size}:".encode() + raster.tobytes()).hexdigest()
                thumbnail = raster.resize((48, 48), Image.Resampling.BOX)
                ink = frozenset(index for index, pixel in enumerate(thumbnail.getdata()) if pixel < 232)
                result.append(Fingerprint(digest, text, ink))
    return result


def similarity(left, right):
    visual = len(left.ink & right.ink) / max(1, len(left.ink | right.ink))
    if left.text and right.text:
        text = len(left.text & right.text) / len(left.text | right.text)
        return 0.60 * text + 0.40 * visual
    return visual


def suggest(before, after):
    left = dict(enumerate(before, 1))
    right = dict(enumerate(after, 1))
    results: dict[PageMatch, float] = {}
    left_counts = Counter(page.sha256 for page in before)
    right_counts = Counter(page.sha256 for page in after)
    right_unique = {page.sha256: number for number, page in right.items() if right_counts[page.sha256] == 1}
    for old, page in list(left.items()):
        if left_counts[page.sha256] == 1 and page.sha256 in right_unique and (page.ink or page.text):
            new = right_unique[page.sha256]
            results[match_kind(old, new, False), old, new] = 1.0
            del left[old], right[new]

    scores = {(old, new): similarity(a, b) for old, a in left.items() for new, b in right.items()}
    left_ranks = {old: sorted(((scores[old, new], new) for new in right), reverse=True) for old in left}
    right_ranks = {new: sorted(((scores[old, new], old) for old in left), reverse=True) for new in right}
    for old, ranked in left_ranks.items():
        if not ranked:
            continue
        score, new = ranked[0]
        reverse = right_ranks[new]
        margin = score - max(ranked[1][0] if len(ranked) > 1 else 0, reverse[1][0] if len(reverse) > 1 else 0)
        if reverse[0][1] == old and score >= MINIMUM_SCORE and margin >= MINIMUM_MARGIN:
            results["EDITED", old, new] = score
            del left[old], right[new]
    for old in left:
        if max((score for score, _ in left_ranks[old]), default=0) <= NOVELTY:
            results["REMOVED", old, None] = 1 - max((score for score, _ in left_ranks[old]), default=0)
    for new in right:
        if max((score for score, _ in right_ranks[new]), default=0) <= NOVELTY:
            results["ADDED", None, new] = 1 - max((score for score, _ in right_ranks[new]), default=0)
    return results


def fixtures(pptx_path=None):
    def page(identity, revision=0, appearance=None):
        return identity, revision, appearance or identity

    for mode in ("text", "scan"):
        for index in range(5):
            a, b, c, d, e = (page(f"{name}{index}") for name in "ABCDE")
            b_edit = page(b[0], 1)
            yield f"{mode}-mixed-{index}", mode, (a, b, c, d), (c, a, b_edit, e)
        original = (page("first", appearance="template"), page("second", appearance="template"), page("unique"))
        yield f"{mode}-duplicate", mode, original, (original[1], original[0], original[2])
        yield f"{mode}-reused-layout", mode, (page("obsolete", appearance="reuse"),), (page("replacement", 1, "reuse"),)

    if pptx_path is not None:
        rendition = PdfReader(pptx_path, strict=True)
        assert len(rendition.pages) >= 3, "Expected at least three exported synthetic slides"
        for index, (old, new) in enumerate((((1, 2, 3), (3, 1, 2)), ((1, 2), (3, 1)))):
            yield f"pptx-rendition-{index}", "pptx", tuple((f"slide-{n}", 0, n) for n in old), tuple((f"slide-{n}", 0, n) for n in new)


def evaluate(pptx_path=None):
    corpus = []
    timings = []
    for name, mode, old, new in fixtures(pptx_path):
        if mode == "pptx":
            rendition = PdfReader(pptx_path, strict=True)
            before, after = (pptx_pdf(rendition, [item[2] for item in spec]) for spec in (old, new))
        else:
            before, after = (synthetic_pdf(spec, mode) for spec in (old, new))
        expected = gold(before, after, old, new)
        started = time.perf_counter()
        left, right = fingerprints(before), fingerprints(after)
        detected = suggest(left, right)
        timings.append((time.perf_counter() - started) * 1000)
        for kind, old, new in expected:
            if old is not None and new is not None:
                assert (left[old - 1].sha256 == right[new - 1].sha256) == (kind != "EDITED"), name
        if mode in {"scan", "text"}:
            assert all(bool(page.text) == (mode == "text") for page in (*left, *right)), name
        assert len({old for _, old, _ in detected if old is not None}) == sum(old is not None for _, old, _ in detected)
        assert len({new for _, _, new in detected if new is not None}) == sum(new is not None for _, _, new in detected)
        corpus.append((name, mode, expected, detected, [hashlib.sha256(pdf).hexdigest() for pdf in (before, after)]))

    def summary(rows):
        metrics = {}
        for kind in KINDS:
            expected_count = sum(sum(item[0] == kind for item in expected) for _, _, expected, _, _ in rows)
            suggested_count = sum(sum(item[0] == kind for item in detected) for _, _, _, detected, _ in rows)
            tp = sum(sum(item[0] == kind for item in expected.intersection(detected)) for _, _, expected, detected, _ in rows)
            metrics[kind] = {"gold": expected_count, "suggested": suggested_count, "true_positive": tp,
                             "precision": tp / suggested_count if suggested_count else None,
                             "recall": tp / expected_count if expected_count else None}
        pairs = [(item, score, item in expected) for _, _, expected, detected, _ in rows
                 for item, score in detected.items() if item[1] is not None and item[2] is not None]
        confident = [correct for _, score, correct in pairs if score >= CONFIDENCE]
        correct_pairs = sum(correct for _, _, correct in pairs)
        return {"by_kind": metrics, "pair_suggestions": len(pairs),
                "pair_precision": correct_pairs / len(pairs) if pairs else None,
                "high_confidence_pairs": len(confident),
                "high_confidence_wrong_pair_rate": confident.count(False) / len(confident) if confident else None,
                "manual_rows_without_suggestions": sum(len(expected) for _, _, expected, _, _ in rows),
                "review_or_correct_suggestion_rows": sum(len(detected) for _, _, _, detected, _ in rows),
                "manual_rows_missing_after_suggestions": sum(len(expected.difference(detected)) for _, _, expected, detected, _ in rows)}

    def sorted_matches(items):
        return sorted(items, key=lambda row: (row[0], row[1] or 0, row[2] or 0))

    return {"edit_rule": "EDITED takes precedence; MOVED means a different 1-based index, including insertion shifts",
            "thresholds": {"fuzzy_score": MINIMUM_SCORE, "fuzzy_margin": MINIMUM_MARGIN, "novelty": NOVELTY, "high_confidence": CONFIDENCE},
            "overall": summary(corpus), "by_source": {mode: summary([row for row in corpus if row[1] == mode])
                                                     for mode in sorted({row[1] for row in corpus})},
            "timing": {"median_ms_per_pair": statistics.median(timings), "max_ms_per_pair": max(timings),
                       "human_editing_time": "unmeasured"},
            "corpus": [{"name": name, "source": mode, "pdf_sha256": hashes, "gold": sorted_matches(expected),
                        "suggestions": [{"match": item, "score": round(detected[item], 4)} for item in sorted_matches(detected)]}
                       for name, mode, expected, detected, hashes in corpus]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-pptx-rehearsal", action="store_true", help="include the local synthetic PPTX rendition")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    path = root / ".tooling/learning-pptx-live-20261105-02/renditions/69f50f7320ae4001ab0af5be55db821b/pdf/source.pdf"
    if args.with_pptx_rehearsal:
        if path.resolve(strict=True) != path:
            raise ValueError("Expected the canonical local synthetic PPTX rendition")
    print(json.dumps(evaluate(path if args.with_pptx_rehearsal else None), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
