"""Offline A1–A8 scoring and an explicitly invoked local SSE runner (A9 external).

Run/score/compare --help describes the CLI. Results are JSON snapshots, checkpointed
after each completed attempt. Resume preserves existing attempts; --force first
retains a backup. No live call happens on import or during scoring/comparison.
"""
from __future__ import annotations

import argparse
import codecs
import hashlib
import importlib.util
import json
import math
import re
import statistics
import threading
import time
import unicodedata
import uuid
from collections import defaultdict
from concurrent import futures
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

try:
    from . import live_retrieval_probe as probe
except ImportError:  # Direct script execution and file-based test imports.
    _spec = importlib.util.spec_from_file_location(
        "live_retrieval_probe", Path(__file__).with_name("live_retrieval_probe.py"))
    probe = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(probe)

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "evals/datasets/rag-v2/cases.jsonl"
CORPUS = ROOT / "evals/corpus/served-chunks.jsonl"
ANSWERED = {"answer", "partial"}
VARIANT_LIMITS = {"form+no_diacritics": .92, "keyword": .85, "slang": .75}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    # "181TC" and "181 tín chỉ" state the same credit count.
    text = re.sub(r"(?<=\d)\s*tc\b", " tin chi", text)
    # Only thousands groups collapse: dates and decimal 2.5 retain boundaries.
    text = re.sub(r"(?<=\d)(?:[.,]|\s+)(?=\d{3}(?:\D|$))", "", text)
    return " ".join(re.findall(r"[a-z0-9]+", text))


_STOP = frozenset("la va cua cho co the duoc khong nhung thi ma o tai tu den khi neu da se hay hoac cac mot nhu".split())


def fact_matches(fact: str, answer: str) -> bool:
    """A required fact is satisfied when the answer states it, wording aside.

    Exact phrase match first. Otherwise every number of the fact must appear in the answer (dates match
    by their numbers: "13 tháng 01 năm 2026" = "13/01/2026") and at least 75% of its other content words
    must appear. The same rule scores v1 and v2, so it never favours one engine.
    """
    needle, haystack = normalize(fact), normalize(answer)
    if not needle:
        return False
    if f" {needle} " in f" {haystack} ":
        return True
    padded = f" {haystack} "
    tokens = [t for t in needle.split() if t not in _STOP]
    numbers = [t for t in tokens if t.isdigit()]
    words = [t for t in tokens if not t.isdigit()]
    if any(f" {t} " not in padded for t in numbers):
        return False
    if not words:
        return bool(numbers)
    # Stems tolerate inflection ("ứng" / "ứng với") at the cost of nothing: whole-word containment.
    hits = sum(1 for t in words if f" {t} " in padded)
    return hits / len(words) >= 0.75


def outcome(final: dict | None) -> str:
    if not final:
        return "error"
    kind = final.get("outcome_kind")
    if kind:
        return kind if kind in ANSWERED | {"clarify", "refuse"} else "error"
    if final.get("response_class") == "system_error" or final.get("status") == "safe_failure":
        return "error"
    if final.get("response_class") == "partial_answer":
        return "partial"
    old = probe.disposition(final)
    if old == "clarification":
        return "clarify"
    if old == "abstained" and final.get("status") == "abstained":
        return "refuse"
    return "answer" if final.get("status") == "answered" else "error"


def citation_ids(final: dict, corpus: list[dict]) -> list[str]:
    """Never infer a chunk from a title alone or from an ambiguous quote."""
    found = set()
    for item in final.get("citations") or []:
        if isinstance(item, str):
            found.add(item)
            continue
        if not isinstance(item, dict):
            continue
        citation = item.get("citation") or item
        chunk_id = citation.get("chunk_id") or item.get("chunk_id")
        if chunk_id:
            found.add(str(chunk_id))
            continue
        quote = citation.get("quote") or citation.get("excerpt") or item.get("quote")
        if not quote or not str(quote).strip():
            continue
        title = citation.get("source_title") or citation.get("title")
        matches = [chunk["chunk_id"] for chunk in corpus
                   if (not title or normalize(title) == normalize(chunk.get("doc_title", "")))
                   and " ".join(str(quote).split()) in
                   " ".join(chunk.get("text", chunk.get("content_text", "")).split())]
        if len(matches) == 1:
            found.add(matches[0])
    return sorted(found)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def writable_path(value: str | Path) -> Path:
    path = Path(value).absolute()
    if ".." in path.parts or any(c in str(path) for c in "*?$"):
        raise ValueError("Ambiguous output path")
    for ancestor in (path, *path.parents):
        if ancestor.exists() and (ancestor.is_symlink() or ancestor.is_junction()):
            raise ValueError("Output crosses a symlink or junction")
    path = path.resolve()
    if path == ROOT or not path.is_relative_to(ROOT):
        raise ValueError("Output must be a file inside the workspace")
    return path


def write_json(path: Path, data: dict, *, replace: bool = False) -> None:
    path = writable_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if not replace:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(content)
        return
    # Exclusive temp creation + atomic rename leaves the previous JSON intact
    # if a process is interrupted while serializing/writing the next checkpoint.
    temporary = writable_path(path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp"))
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(content)
        stream.flush()
        import os
        os.fsync(stream.fileno())
    temporary.replace(path)


class RateLimit:
    """A 429 on any worker pauses all subsequent requests, including new chats."""
    def __init__(self):
        self.lock = threading.Lock()
        self.until = 0.0

    def wait(self):
        while True:
            with self.lock:
                delay = self.until - time.monotonic()
            if delay <= 0:
                return
            time.sleep(min(delay, 1))

    def defer(self, header: str = "5"):
        try:
            seconds = float(header)
        except ValueError:
            try:
                seconds = (parsedate_to_datetime(header) - datetime.now(UTC)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                seconds = 5
        if not math.isfinite(seconds):
            seconds = 5
        with self.lock:
            self.until = max(self.until, time.monotonic() + max(0, seconds) + .3)


class LimitedClient:
    """Adapter lets the existing probe.send own POST retry behavior."""
    def __init__(self, client, limiter):
        self.client, self.limiter = client, limiter

    def post(self, path, **kwargs):
        self.limiter.wait()
        response = self.client.post(path, **kwargs)
        if response.status_code == 429:
            # The probe understands only integer Retry-After. Convert dates too;
            # its capped sleep is followed by the shared full-duration gate.
            self.limiter.defer(response.headers.get("Retry-After", "5"))
            response.headers["Retry-After"] = "0"
        return response


def _frame(block: str) -> tuple[str, dict]:
    event = "message"
    data = []
    for line in block.splitlines():
        key, _, value = line.partition(":")
        value = value.removeprefix(" ")
        if key == "event":
            event = value
        elif key == "data":
            data.append(value)
    return event, json.loads("\n".join(data)) if data else {}


def stream_reply(client, path, question, limiter, started, record):
    for attempt in range(6):
        limiter.wait()
        with client.stream("POST", path, json={"content": question}) as response:
            record["http_status"] = response.status_code
            if response.status_code == 429:
                limiter.defer(response.headers.get("Retry-After", "5"))
                continue
            response.raise_for_status()
            decoder = codecs.getincrementaldecoder("utf-8")()
            buffer = ""
            for raw in response.iter_bytes():
                if not raw:
                    continue
                if record["first_byte_seconds"] is None:
                    record["first_byte_seconds"] = time.perf_counter() - started
                buffer += decoder.decode(raw)
                # Normalize only complete CRLF pairs; an isolated CR at the end
                # of a transport chunk must wait for its following LF.
                buffer = buffer.replace("\r\n", "\n")
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    event, data = _frame(block)
                    if record["first_content_seconds"] is None and (
                        (event == "message.delta" and data.get("delta")) or
                        (event == "message.completed" and data.get("content"))
                    ):
                        record["first_content_seconds"] = time.perf_counter() - started
                    if event == "message.completed":
                        # Reuse the probe's final-event extraction, also for
                        # multiline SSE data and CRLF streams.
                        return probe.final_event("event: message.completed\ndata: " + json.dumps(data) + "\n\n")
                    if event == "message.failed":
                        record["error"] = "StreamFailed"
            record["error"] = record["error"] or "MissingFinalEvent"
            return None
    record["error"] = "RateLimitExhausted"
    return None


def run_case(client, case: dict, repeat: int, corpus: list[dict], limiter: RateLimit,
             api_log: Path | None = None) -> dict:
    started = time.perf_counter()
    record = {"case_id": case["case_id"], "repeat": repeat, "outcome_class": "error",
              "answer_text": "", "citation_chunk_ids": [], "citation_count": 0,
              "http_status": None, "error": None, "final_event": False,
              "first_byte_seconds": None, "first_content_seconds": None}
    try:
        conversation = probe.send(LimitedClient(client, limiter), "/v1/conversations", {"mode": "temporary"})
        record["http_status"] = conversation.status_code
        conversation.raise_for_status()
        conversation_id = conversation.json()["id"]
        record["conversation_id"] = conversation_id
        offset = api_log.stat().st_size if api_log else 0
        final = stream_reply(client, f"/v1/conversations/{conversation_id}/messages:stream",
                             case["question"], limiter, started, record)
        if final is not None:
            record.update(outcome_class=outcome(final), final_event=True,
                          answer_text=final.get("content", ""),
                          citation_chunk_ids=citation_ids(final, corpus),
                          citation_count=len(final.get("citations") or []))
            if record["outcome_class"] == "error":
                record["error"] = "TerminalError"
        if api_log:
            # Uncorrelated log lines are deliberately ignored with concurrency.
            with api_log.open("rb") as log:
                log.seek(offset)
                lines = log.read().decode("utf-8", "replace").splitlines()
            record["trace"] = trace_from_log(lines, conversation_id, case, corpus)
    except Exception as error:  # noqa: BLE001 - record type only, never credential-bearing messages.
        record["outcome_class"] = "error"
        record["error"] = type(error).__name__
    record["seconds"] = time.perf_counter() - started
    return record


def trace_from_log(lines, conversation_id, case, corpus):
    gold_ids = {gold["chunk_id"] for gold in case.get("gold", [])}
    labels = [chunk["section_label"] for chunk in corpus
              if chunk["chunk_id"] in gold_ids and chunk.get("section_label")]
    trace = {}
    for line in lines:
        if conversation_id not in line:
            continue
        for label in ("CORPUS_MISSING", "INGEST", "RETRIEVAL", "RERANK", "GENERATION", "VERIFICATION"):
            if re.search(r"(?:failure_layer|error_label)[=: '\"]+" + label + r"\b", line):
                trace["failure_layer"] = label
        if "retrieval_pool " in line and labels:
            pool = probe.parse_pool(line.split("retrieval_pool ", 1)[1])
            if pool:
                trace.update(in_pool=probe.hit(pool[0] + pool[1], labels), in_chosen=probe.hit(pool[2], labels))
    return trace


def fingerprint(cases):
    return hashlib.sha256(json.dumps(cases, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def prepare_run(path: Path, cases: list[dict], base_url: str, force=False) -> dict:
    metadata = {"cases_sha256": fingerprint(cases), "base_url": base_url.rstrip("/")}
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        if previous.get("schema") != "rag-v2-run/1":
            raise ValueError("Existing output is not a runner checkpoint; choose a new path")
        if not force:
            if previous.get("metadata") != metadata:
                raise ValueError("Resume dataset/base URL differs; choose a new output or --force")
            keys = [(row["case_id"], row["repeat"]) for row in previous["records"]]
            if len(keys) != len(set(keys)):
                raise ValueError("Duplicate attempts in checkpoint")
            return previous
        backup = writable_path(path.with_name(path.name + ".backup-" + uuid.uuid4().hex + ".json"))
        # Preserve the exact old bytes before --force replaces any result.
        with backup.open("xb") as target:
            target.write(path.read_bytes())
    result = {"schema": "rag-v2-run/1", "metadata": metadata, "records": []}
    write_json(path, result, replace=path.exists())
    return result


def run(args):
    parsed = urlparse(args.base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username:
        raise ValueError("The runner accepts only a local HTTP runtime")
    cases = [case for case in read_jsonl(Path(args.cases))
             if (args.split == "all" or case["split"] == args.split)
             and (not args.family or case["family"] == args.family)]
    cases = cases[:args.limit] if args.limit else cases
    if not cases or len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("Empty selection or duplicate case IDs")
    corpus = read_jsonl(Path(args.corpus))
    path = writable_path(args.out)
    result = prepare_run(path, cases, args.base_url, args.force)
    done = {(row["case_id"], row["repeat"]) for row in result["records"]}
    jobs = [(case, repeat) for repeat in range(1, args.repeat + 1) for case in cases
            if (case["case_id"], repeat) not in done]
    if not jobs:
        print(f"Already saved: {len(done)} attempts")
        return
    limiter = RateLimit()
    checkpoint_lock = threading.Lock()
    # Credentials stay in local memory; never print responses from login.
    credentials = json.loads((probe.STATE / "owner-credentials.json").read_text(encoding="utf-8"))
    with httpx.Client(base_url=args.base_url, trust_env=False, timeout=args.timeout,
                      follow_redirects=False) as client:
        login = probe.send(LimitedClient(client, limiter), probe.API + "/session",
                           {key: credentials[key] for key in ("username", "password")})
        if login.status_code != 200:
            raise ValueError(f"Login failed: HTTP {login.status_code}")
        del credentials

        def worker(job):
            row = run_case(client, job[0], job[1], corpus, limiter,
                           Path(args.api_log) if args.api_log else None)
            with checkpoint_lock:
                result["records"].append(row)
                write_json(path, result, replace=True)
            return row

        # At most concurrency jobs are submitted. Each completed worker saves
        # before returning; interruption cancels queued jobs and retains in-flight
        # results before the HTTP client closes.
        with futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            pending = set()
            todo = iter(jobs)
            try:
                for _ in range(min(args.concurrency, len(jobs))):
                    pending.add(executor.submit(worker, next(todo)))
                while pending:
                    finished, pending = futures.wait(pending, return_when=futures.FIRST_COMPLETED)
                    for future in finished:
                        future.result()
                        job = next(todo, None)
                        if job is not None:
                            pending.add(executor.submit(worker, job))
            except BaseException:
                for future in pending:
                    future.cancel()
                raise
    print(f"Saved {len(result['records'])} attempts: {path}")


def percentile(values, fraction=.95):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)] if ordered else None


def ratio(numerator, denominator, threshold, *, maximum=False, strict=False):
    value = numerator / denominator if denominator else None
    passed = None if value is None else (
        value < threshold if strict else value <= threshold if maximum else value >= threshold)
    return {"numerator": numerator, "denominator": denominator, "value": value,
            "threshold": threshold, "passed": passed}


def infra_error(row):
    return (row.get("outcome_class") == "error" or bool(row.get("error"))
            or row.get("final_event") is not True or (row.get("http_status") or 200) >= 400)


def error_label(case, row):
    if infra_error(row):
        return "INFRA"
    kind = row["outcome_class"]
    if case["expected"] == "answer" and kind == "refuse":
        return "OVER_REFUSE"
    if case["expected"] in {"abstain", "clarify"} and kind in ANSWERED:
        return "OVER_ANSWER"
    trace = row.get("trace") or {}
    if trace.get("failure_layer") in {"CORPUS_MISSING", "INGEST", "RETRIEVAL", "RERANK", "GENERATION", "VERIFICATION"}:
        return trace["failure_layer"]
    if trace.get("in_pool") is False or trace.get("in_chosen") is False:
        return "RETRIEVAL"
    return "UNLABELED"


_CHUNK_TEXT: dict[str, str] = {}


def cites_gold(case, cited_ids) -> bool:
    """A citation is correct when it is a gold chunk or another chunk that contains a gold quote verbatim.

    The corpus holds the same table or notice in several chunks (per-semester and per-prerequisite views);
    demanding the one chunk the case writer happened to pick scores a correct citation as wrong.
    """
    gold = {item["chunk_id"] for item in case.get("gold", [])}
    if gold & set(cited_ids):
        return True
    if not _CHUNK_TEXT and CORPUS.exists():
        for line in CORPUS.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            _CHUNK_TEXT[row["chunk_id"]] = " ".join(row.get("text", row.get("content_text", "")).split())
    quotes = [" ".join(item["quote"].split()) for item in case.get("gold", []) if item.get("quote")]
    return any(quote in _CHUNK_TEXT.get(chunk_id, "") for chunk_id in cited_ids for quote in quotes)


def metrics(rows, cases):
    answers = [row for row in rows if cases[row["case_id"]]["expected"] == "answer"]
    negative = [row for row in rows if cases[row["case_id"]]["expected"] in {"abstain", "clarify"}]
    displayed = [row for row in rows if row["outcome_class"] in ANSWERED]
    incorrect, unsourced, wrong_gold, failures = [], [], [], []
    for row in rows:
        case = cases[row["case_id"]]
        text = row.get("answer_text", "")
        answered = row["outcome_class"] in ANSWERED
        missing = [fact for fact in case.get("required_facts", []) if not fact_matches(fact, text)]
        forbidden = [fact for fact in case.get("forbidden_facts", []) if fact_matches(fact, text)]
        reasons = []
        key = {"case_id": row["case_id"], "repeat": row.get("repeat", 1)}
        if case["expected"] == "answer" and answered and (missing or forbidden):
            incorrect.append(key | {"missing_facts": missing, "forbidden_facts": forbidden})
            reasons.append("A1")
        if answered and not row.get("citation_count", len(row.get("citation_chunk_ids", []))):
            unsourced.append(key)
            reasons.append("A2")
        if answered and not cites_gold(case, row.get("citation_chunk_ids", [])):
            wrong_gold.append(key)
            reasons.append("A5")
        if case["expected"] != "answer" and row["outcome_class"] not in {"refuse", "clarify"}:
            reasons.append("A3")
        if case["expected"] == "answer" and not answered:
            reasons.append("A4")
        if infra_error(row):
            reasons.append("A7")
        if reasons:
            failures.append(key | {"criteria": reasons, "label": error_label(case, row)})
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["case_id"]].append(row["outcome_class"])
    repeated = {key: values for key, values in grouped.items() if len(values) >= 2}
    inconsistent = [key for key, values in repeated.items() if len(set(values)) != 1]
    # A6 failures also receive exactly one case label if not already attributed.
    for case_id in inconsistent:
        if not any(failure["case_id"] == case_id for failure in failures):
            failures.append({"case_id": case_id, "repeat": None, "criteria": ["A6"], "label": "UNLABELED"})
    variants = {}
    for variant, threshold in VARIANT_LIMITS.items():
        names = variant.split("+")
        subset = [row for row in answers if cases[row["case_id"]]["variant"] in names]
        variants[variant] = ratio(sum(row["outcome_class"] in ANSWERED for row in subset), len(subset), threshold)
    seconds = [row["seconds"] for row in rows if isinstance(row.get("seconds"), (int, float))]
    first_bytes = [row["first_byte_seconds"] for row in rows if row.get("first_byte_seconds") is not None]
    first_content = [row["first_content_seconds"] for row in rows if row.get("first_content_seconds") is not None]
    timing = {"median_seconds": statistics.median(seconds) if seconds else None,
              "p95_seconds": percentile(seconds),
              "first_byte_median_seconds": statistics.median(first_bytes) if first_bytes else None,
              "first_byte_p95_seconds": percentile(first_bytes),
              "first_content_median_seconds": statistics.median(first_content) if first_content else None,
              "first_content_p95_seconds": percentile(first_content),
              "thresholds_seconds": {"median": 6, "p95": 12, "first_byte_median": 2},
              "samples": len(seconds), "first_byte_samples": len(first_bytes)}
    timing["passed"] = (timing["median_seconds"] <= 6 and timing["p95_seconds"] <= 12
                        and timing["first_byte_median_seconds"] <= 2) if (
                            rows and len(seconds) == len(rows) and len(first_bytes) == len(rows)) else None
    variant_passes = [value["passed"] for value in variants.values()]
    return {
        "A1": ratio(len(incorrect), len(answers), .02, maximum=True) | {"incorrect": incorrect},
        "A2": {"value": len(unsourced), "threshold": 0, "passed": not unsourced if displayed else None,
               "proxy": "Displayed answer/partial with zero citations; not claim-level verification", "cases": unsourced},
        "A3": ratio(sum(row["outcome_class"] in {"refuse", "clarify"} for row in negative), len(negative), .98),
        "A4": {"by_variant": variants, "passed": False if False in variant_passes else
               None if None in variant_passes else True},
        "A5": ratio(len(displayed) - len(wrong_gold), len(displayed), .95) | {"misses": wrong_gold},
        "A6": ratio(len(repeated) - len(inconsistent), len(repeated), .95) | {"inconsistent_cases": inconsistent},
        "A7": ratio(sum(infra_error(row) for row in rows), len(rows), .01, maximum=True, strict=True),
        "A8": timing,
        "A9": {"passed": None, "status": "EXTERNAL", "reason": "Separate safety/routing/tool campaign required"},
        "failures": failures,
    }


def score_records(records, cases, split="holdout"):
    selected = {case["case_id"]: case for case in cases if split == "all" or case["split"] == split}
    if not selected:
        raise ValueError("No cases in selected split")
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("Duplicate case IDs")
    unknown = {row["case_id"] for row in records} - {case["case_id"] for case in cases}
    if unknown:
        raise ValueError("Results contain unknown case IDs")
    rows = [row for row in records if row["case_id"] in selected]
    seen = set()
    for row in rows:
        key = (row.get("source_run"), row["case_id"], row.get("repeat", 1))
        if key in seen:
            raise ValueError("Duplicate attempt within a result source")
        seen.add(key)
        if row.get("outcome_class") not in ANSWERED | {"refuse", "clarify", "error"}:
            raise ValueError("Invalid outcome_class")
    report = {"schema": "rag-v2-score/1", "split": split, "metrics": metrics(rows, selected),
              "by_family": {}, "by_variant": {}, "case_outcomes": {}}
    for field in ("family", "variant"):
        for value in sorted({case[field] for case in selected.values()}):
            subset = [row for row in rows if selected[row["case_id"]][field] == value]
            report["by_" + field][value] = metrics(subset, selected)
    for case_id in sorted(selected):
        report["case_outcomes"][case_id] = [{"repeat": row.get("repeat", 1), "outcome_class": row["outcome_class"],
                                            "result_sha256": fingerprint({key: row.get(key) for key in (
                                                "outcome_class", "answer_text", "citation_chunk_ids", "error")})}
                                            for row in sorted(rows, key=lambda row: row.get("repeat", 1))
                                            if row["case_id"] == case_id]
    counts = {key: len(value) for key, value in report["case_outcomes"].items()}
    report["coverage"] = {"selected_cases": len(selected), "attempts": len(rows),
                          "missing_cases": [key for key, count in counts.items() if count == 0],
                          "fewer_than_three_repeats": [key for key, count in counts.items() if count < 3],
                          "holdout_three_repeats_complete": split == "holdout" and all(count >= 3 for count in counts.values())}
    return report


def status(metric):
    if metric.get("status") == "EXTERNAL":
        return "EXTERNAL"
    return {True: "PASS", False: "FAIL", None: "NOT_MEASURED"}[metric.get("passed")]


def show_metrics(title, values):
    print(title)
    print("criterion | status | measurements")
    for criterion in (f"A{i}" for i in range(1, 10)):
        metric = values[criterion]
        detail = {key: value for key, value in metric.items() if key not in
                  {"incorrect", "misses", "cases", "inconsistent_cases", "passed"}}
        print(f"{criterion} | {status(metric)} | {json.dumps(detail, ensure_ascii=False)}")


def load_report(path, cases, split):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data if data.get("schema") == "rag-v2-score/1" else score_records(data["records"], cases, split)


def compare_reports(a, b):
    if a["split"] != b["split"]:
        raise ValueError("Cannot compare different splits")
    changed = []
    for case_id in sorted(set(a["case_outcomes"]) | set(b["case_outcomes"])):
        left, right = a["case_outcomes"].get(case_id, []), b["case_outcomes"].get(case_id, [])
        if left != right:
            changed.append({"case_id": case_id, "a": left, "b": right})
    return {"criteria": {f"A{i}": {"a": a["metrics"][f"A{i}"], "b": b["metrics"][f"A{i}"]} for i in range(1, 10)},
            "changed_cases": changed}


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    live = sub.add_parser("run", help="Explicit live local run; spends configured provider budget")
    live.add_argument("--base-url", default="http://127.0.0.1:8015")
    live.add_argument("--split", choices=("dev", "holdout", "all"), default="dev")
    live.add_argument("--repeat", type=positive, default=3)
    live.add_argument("--out", required=True)
    live.add_argument("--limit", type=positive)
    live.add_argument("--family")
    live.add_argument("--concurrency", type=positive, default=2)
    live.add_argument("--timeout", type=positive, default=120)
    live.add_argument("--cases", default=str(CASES))
    live.add_argument("--corpus", default=str(CORPUS))
    live.add_argument("--api-log", help="Optional log; only conversation-correlated lines are attributed")
    live.add_argument("--force", action="store_true", help="Restart, retaining the previous JSON in a unique backup")
    scoring = sub.add_parser("score")
    scoring.add_argument("--results", action="append", required=True)
    scoring.add_argument("--cases", required=True)
    scoring.add_argument("--split", choices=("dev", "holdout", "all"), default="holdout")
    scoring.add_argument("--out", help="Default: first results filename + .score.json; must not exist")
    comparison = sub.add_parser("compare")
    comparison.add_argument("--a", required=True)
    comparison.add_argument("--b", required=True)
    comparison.add_argument("--cases", default=str(CASES), help="Required for raw result inputs, unused for scored reports")
    comparison.add_argument("--split", choices=("dev", "holdout", "all"), default="holdout")
    comparison.add_argument("--out", help="Optional new comparison JSON")
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            run(args)
        elif args.command == "score":
            records = [row | {"source_run": str(Path(path).resolve())} for path in args.results
                       for row in json.loads(Path(path).read_text(encoding="utf-8"))["records"]]
            report = score_records(records, read_jsonl(Path(args.cases)), args.split)
            output = writable_path(args.out or (args.results[0] + ".score.json"))
            write_json(output, report)
            show_metrics("Overall", report["metrics"])
            for field in ("family", "variant"):
                for key, values in report["by_" + field].items():
                    show_metrics(f"{field}: {key}", values)
            print("Coverage: " + json.dumps(report["coverage"], ensure_ascii=False))
            print(f"JSON: {output}")
        else:
            inputs = [json.loads(Path(path).read_text(encoding="utf-8")) for path in (args.a, args.b)]
            cases = read_jsonl(Path(args.cases)) if any(data.get("schema") != "rag-v2-score/1" for data in inputs) else []
            a, b = [load_report(path, cases, args.split) for path in (args.a, args.b)]
            report = compare_reports(a, b)
            print("criterion | v1 (a) | v2 (b)")
            for criterion, pair in report["criteria"].items():
                print(f"{criterion} | {status(pair['a'])} {json.dumps(pair['a'], ensure_ascii=False)} | "
                      f"{status(pair['b'])} {json.dumps(pair['b'], ensure_ascii=False)}")
            print("Changed cases: " + json.dumps(report["changed_cases"], ensure_ascii=False))
            if args.out:
                write_json(writable_path(args.out), report)
    except (ValueError, OSError, KeyError, TypeError, httpx.HTTPError) as error:
        # No exception message here: paths/data/HTTP errors can contain secrets.
        parser.exit(2, f"{type(error).__name__}: invalid input, output conflict, or local runtime failure\n")


if __name__ == "__main__":
    main()
