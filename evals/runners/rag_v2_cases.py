"""Validate, merge and summarize RAG v2 cases offline (standard library only)."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evals/datasets/rag-v2"
VARIANTS = ("form", "no_diacritics", "keyword", "slang")
FAMILIES = {"quy_che", "so_tay", "hoc_phi", "thong_bao", "ctdt", "khac",
            "ngoai_pham_vi", "mo_ho", "gan_mien_vang"}
FIELDS = {"case_id", "split", "family", "variant", "question", "expected",
          "gold", "required_facts", "forbidden_facts", "group_id"}


def _string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _strings(value: Any) -> bool:
    return isinstance(value, list) and all(_string(item) for item in value)


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.casefold().replace("đ", "d"))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def _issue(case_id: str, code: str, message: str) -> dict[str, str]:
    return {"case_id": case_id, "code": code, "message": message}


def validate_cases(cases: Sequence[Any], chunks: Sequence[Any]) -> list[dict[str, str]]:
    """Return all integrity errors; repeated group IDs are the four paraphrases.

    The exporter calls content_text ``text``. Both spellings are accepted, but
    conflicting values fail validation. Quotes and facts are never normalized.
    """
    errors: list[dict[str, str]] = []
    catalog: dict[str, tuple[str, Any]] = {}
    for index, chunk in enumerate(chunks, 1):
        label = f"<corpus:{index}>"
        if not isinstance(chunk, dict) or not _string(chunk.get("chunk_id")):
            errors.append(_issue(label, "CORPUS_SCHEMA", "chunk_id must be a nonempty string"))
            continue
        text = chunk.get("content_text", chunk.get("text"))
        if not _string(text):
            errors.append(_issue(label, "CORPUS_SCHEMA", "content_text (or exported text) is required"))
            continue
        if "content_text" in chunk and "text" in chunk and chunk["content_text"] != chunk["text"]:
            errors.append(_issue(label, "CORPUS_TEXT_CONFLICT", chunk["chunk_id"]))
        if chunk["chunk_id"] in catalog:
            errors.append(_issue(label, "DUPLICATE_CHUNK_ID", chunk["chunk_id"]))
        catalog[chunk["chunk_id"]] = (text, chunk.get("doc_family"))
    if not catalog:
        errors.append(_issue("<corpus>", "EMPTY_CORPUS", "No usable corpus chunks"))
    if not cases:
        errors.append(_issue("<dataset>", "EMPTY_DATASET", "No cases"))
    texts = [text for text, _ in catalog.values()]
    folded_texts = [_fold(text) for text in texts]
    seen_ids: set[str] = set()
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, case in enumerate(cases, 1):
        label = case.get("case_id") if isinstance(case, dict) else None
        label = label if _string(label) else f"<case:{index}>"

        def error(code: str, message: str, case_id: str = label) -> None:
            errors.append(_issue(case_id, code, message))

        if not isinstance(case, dict):
            error("CASE_SCHEMA", "Case must be an object")
            continue
        missing = FIELDS - case.keys()
        if missing:
            error("MISSING_FIELDS", ", ".join(sorted(missing)))
        for field in ("case_id", "group_id", "question"):
            if not _string(case.get(field)):
                error("CASE_SCHEMA", f"{field} must be a nonempty string")
        for field, allowed in (("split", ("", "dev", "holdout")), ("family", tuple(FAMILIES)),
                               ("variant", VARIANTS), ("expected", ("answer", "abstain", "clarify"))):
            if not isinstance(case.get(field), str) or case[field] not in allowed:
                error("CASE_SCHEMA", f"Invalid {field}")
        for field in ("required_facts", "forbidden_facts"):
            if not _strings(case.get(field)):
                error("CASE_SCHEMA", f"{field} must be a list of nonempty strings")
        case_id = case.get("case_id")
        if _string(case_id):
            if case_id in seen_ids:
                error("DUPLICATE_CASE_ID", case_id)
            seen_ids.add(case_id)
        if _string(case.get("group_id")):
            groups[case["group_id"]].append(case)
        question = case.get("question")
        if isinstance(question, str):
            if case.get("variant") == "no_diacritics" and not question.isascii():
                error("NON_ASCII_QUESTION", "no_diacritics question must be ASCII")
            if (case.get("expected") == "answer" and case.get("variant") == "keyword"
                    and not 2 <= len(question.split()) <= 6):
                error("KEYWORD_LENGTH", "Answer keywords must contain 2–6 words")
        gold = case.get("gold")
        gold_texts: list[str] = []
        if not isinstance(gold, list):
            error("CASE_SCHEMA", "gold must be a list")
        else:
            for number, ref in enumerate(gold):
                if (not isinstance(ref, dict) or not _string(ref.get("chunk_id"))
                        or not _string(ref.get("quote"))):
                    error("GOLD_SCHEMA", f"gold[{number}] needs chunk_id and quote strings")
                    continue
                quote = ref["quote"]
                if not 20 <= len(quote) <= 300:
                    error("QUOTE_LENGTH", f"gold[{number}].quote must contain 20–300 characters")
                source = catalog.get(ref["chunk_id"])
                if source is None:
                    error("UNKNOWN_CHUNK", ref["chunk_id"])
                    continue
                text, family = source
                gold_texts.append(text)
                if quote not in text:
                    error("QUOTE_NOT_VERBATIM", f"gold[{number}] is absent from {ref['chunk_id']}")
                if family is not None and family != case.get("family"):
                    error("GOLD_FAMILY_MISMATCH", ref["chunk_id"])
        if case.get("expected") == "answer":
            if not isinstance(gold, list) or not gold:
                error("ANSWER_WITHOUT_GOLD", "Answer cases need gold evidence")
            if _strings(case.get("required_facts")) and not 1 <= len(case["required_facts"]) <= 4:
                error("REQUIRED_FACT_COUNT", "Answer cases need 1–4 required facts")
        required = case.get("required_facts")
        forbidden = case.get("forbidden_facts")
        if _strings(required):
            for fact in required:
                if not any(fact in text for text in gold_texts):
                    error("REQUIRED_FACT_NOT_GOLD", repr(fact))
        if _strings(forbidden):
            for fact in forbidden:
                if _strings(required) and any(fact in required_fact for required_fact in required):
                    error("FORBIDDEN_REQUIRED_OVERLAP", repr(fact))
                if not any(fact in text for text in texts):
                    error("FORBIDDEN_FACT_NOT_CORPUS", repr(fact))
        needs_absence = case.get("expected") == "abstain" and case.get("family") == "gan_mien_vang"
        absent = case.get("absent_terms")
        if needs_absence or "absent_terms" in case:
            if not _strings(absent) or (needs_absence and not absent):
                error("ABSENT_TERMS_SCHEMA", "Near-domain abstentions need nonempty absent_terms")
            if _strings(absent):
                for term in absent:
                    folded = _fold(term)
                    if not folded or any(folded in text for text in folded_texts):
                        error("ABSENT_TERM_PRESENT", repr(term))
    for group_id, members in groups.items():
        variants = [member.get("variant") for member in members]
        answer_group = any(member.get("expected") == "answer" for member in members)
        codes: list[tuple[str, str]] = []
        # Lists rather than sets keep malformed (e.g. list-valued) fields safe.
        if any(variants.count(variant) > 1 for variant in variants):
            codes.append(("DUPLICATE_GROUP_VARIANT", group_id))
        if answer_group:
            if len(members) != 4 or any(variants.count(v) != 1 for v in VARIANTS):
                codes.append(("ANSWER_GROUP_VARIANTS", f"{group_id} needs exactly {', '.join(VARIANTS)}"))
            if any(any(member.get(field) != members[0].get(field) for member in members)
                   for field in ("expected", "family", "split")):
                codes.append(("INCONSISTENT_GROUP", group_id))
        elif len(members) != 1:
            codes.append(("DUPLICATE_GROUP_ID", "Non-answer cases must have their own group_id"))
        for member in members:
            label = member.get("case_id")
            for code, message in codes:
                errors.append(_issue(label if _string(label) else "<case>", code, message))
    return errors


def split_for_group(group_id: str) -> str:
    bucket = int.from_bytes(hashlib.sha256(group_id.encode("utf-8")).digest()[:8], "big") % 10
    return "dev" if bucket < 7 else "holdout"


def case_stats(cases: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {"case_count": len(cases), "group_count": len({case["group_id"] for case in cases}),
            "counts": {field: dict(sorted(Counter(case[field] for case in cases).items()))
                       for field in ("split", "family", "variant", "expected")}}


def merge_cases(cases: Sequence[Any], chunks: Sequence[Any]) -> tuple[bytes, dict[str, Any]]:
    errors = validate_cases(cases, chunks)
    if errors:
        raise ValueError("Cannot merge invalid cases")
    merged = [dict(case, split=split_for_group(case["group_id"]))
              for case in sorted(cases, key=lambda case: case["case_id"])]
    payload = "".join(json.dumps(case, ensure_ascii=False, separators=(",", ":")) + "\n"
                      for case in merged).encode("utf-8")
    return payload, {**case_stats(merged), "sha256": hashlib.sha256(payload).hexdigest(),
                     "split_algorithm": "sha256(group_id UTF-8), first 8 bytes big-endian, mod 10 < 7 => dev"}


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_jsonl(path: Path) -> tuple[list[Any], list[dict[str, str]]]:
    records: list[Any] = []
    errors: list[dict[str, str]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return [], [_issue(str(path), "READ_ERROR", str(exc))]
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line, object_pairs_hook=_unique))
        except ValueError as exc:
            errors.append(_issue(f"{path}:{number}", "INVALID_JSON", str(exc)))
    return records, errors


def _write_outputs(output: Path, manifest: Path, payload: bytes, report: dict[str, Any], *,
                   inputs: Sequence[Path], force: bool) -> None:
    destinations = [output.resolve(), manifest.resolve()]
    protected = {path.resolve() for path in inputs}
    if destinations[0] == destinations[1]:
        raise ValueError("Output and manifest must be distinct")
    # Check both targets before opening either one, including existing symlinks.
    for path in destinations:
        if not path.is_relative_to(ROOT) or path == ROOT or path in protected:
            raise ValueError(f"Unsafe output destination: {path}")
        if not path.parent.is_dir():
            raise ValueError(f"Output parent does not exist: {path.parent}")
        if path.exists() and (not force or not path.is_file()):
            raise ValueError(f"Refusing to overwrite {path}; use --force for existing files")
    mode = "wb" if force else "xb"
    manifest_bytes = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    for path, data in zip(destinations, (payload, manifest_bytes)):
        with path.open(mode) as stream:
            stream.write(data)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "merge", "stats"):
        sub = commands.add_parser(command)
        sub.add_argument("--shards-dir", type=Path, default=DATASET / "shards")
        sub.add_argument("--corpus", type=Path, default=ROOT / "evals/corpus/served-chunks.jsonl")
        if command == "merge":
            sub.add_argument("--output", type=Path, default=DATASET / "cases.jsonl")
            sub.add_argument("--manifest", type=Path, default=None,
                             help="Default: output filename with .manifest.json suffix")
            sub.add_argument("--force", action="store_true")
        if command == "stats":
            sub.add_argument("--cases", type=Path, help="Summarize this file instead of shards")
    args = parser.parse_args(argv)
    try:
        paths = ([args.cases] if args.command == "stats" and args.cases is not None
                 else sorted(args.shards_dir.glob("*.jsonl")))
        cases: list[Any] = []
        errors: list[dict[str, str]] = []
        for path in paths:
            records, problems = read_jsonl(path)
            cases.extend(records)
            errors.extend(problems)
        chunks, problems = read_jsonl(args.corpus)
        errors.extend(problems)
        errors.extend(validate_cases(cases, chunks))
        if errors:
            for error in errors:
                print(f"{error['case_id']}: {error['code']}: {error['message']}", file=sys.stderr)
            return 1
        if args.command == "merge":
            payload, report = merge_cases(cases, chunks)
            manifest = args.manifest if args.manifest is not None else args.output.with_suffix(".manifest.json")
            _write_outputs(args.output, manifest, payload, report, inputs=[args.corpus, *paths], force=args.force)
        else:
            report = case_stats(cases)
        print(json.dumps({"status": "ok", **report}, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"<dataset>: INPUT_OUTPUT_ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
