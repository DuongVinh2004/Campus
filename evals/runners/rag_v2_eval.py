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
import os
import re
import statistics
import subprocess
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

try:
    from . import rag_v2_scoring as scoring
except ImportError:
    _score_spec = importlib.util.spec_from_file_location(
        "rag_v2_scoring", Path(__file__).with_name("rag_v2_scoring.py"))
    scoring = importlib.util.module_from_spec(_score_spec)
    _score_spec.loader.exec_module(scoring)

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "evals/datasets/rag-v2/cases.jsonl"
CORPUS = ROOT / "evals/corpus/served-chunks.jsonl"
ANSWERED = {"answer", "partial"}
VARIANT_LIMITS = {"form+no_diacritics": .92, "keyword": .85, "slang": .75}


# Backward-compatible imports; all decisions live in the pure shared scorer.
normalize = scoring.normalize
fact_matches = scoring.fact_matches


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
        record["http_attempts"] = attempt + 1
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
              "attempt_index": 1,
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
            texts = {c["chunk_id"]: c.get("text", c.get("content_text", "")) for c in corpus}
            if all(uid in texts for uid in record["citation_chunk_ids"]) and (
                    record["citation_chunk_ids"] or not record["citation_count"]):
                record["cited_texts"] = [texts[uid] for uid in record["citation_chunk_ids"]]
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


def campaign_manifest(cases, base_url, engine):
    def git(*args):
        try:
            return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.DEVNULL,
                                           text=True, timeout=5).strip()
        except (OSError, subprocess.SubprocessError):
            return None
    # Only non-secret switches, validated against explicit values, enter evidence.
    flags = {k: os.environ[k] for k in ("CAMPUS247_RAG_V2_ENABLED", "CAMPUS247_RAG_V2_DEBUG")
             if os.environ.get(k) in {"0", "1", "true", "false"}}
    if os.environ.get("CAMPUS247_RAG_ENGINE") in {"v1", "v2"}:
        flags["CAMPUS247_RAG_ENGINE"] = os.environ["CAMPUS247_RAG_ENGINE"]
    return {"cases_sha256": fingerprint(cases), "base_url": base_url.rstrip("/"), "engine": engine,
            "git_commit": git("rev-parse", "HEAD"), "git_branch": git("branch", "--show-current"),
            "started_at": datetime.now(UTC).isoformat(), "campaign_id": uuid.uuid4().hex,
            "environment_flags": flags}


def prepare_run(path: Path, cases: list[dict], base_url: str, force=False, *, engine="v2") -> dict:
    identity = {"cases_sha256": fingerprint(cases), "base_url": base_url.rstrip("/"), "engine": engine}
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        if previous.get("schema") != "rag-v2-run/1":
            raise ValueError("Existing output is not a runner checkpoint; choose a new path")
        if not force:
            if any(previous.get("metadata", {}).get(k) != v for k, v in identity.items()):
                raise ValueError("Resume dataset/base URL differs; choose a new output or --force")
            keys = [(row["case_id"], row["repeat"]) for row in previous["records"]]
            if len(keys) != len(set(keys)):
                raise ValueError("Duplicate attempts in checkpoint")
            return previous
        backup = writable_path(path.with_name(path.name + ".backup-" + uuid.uuid4().hex + ".json"))
        # Preserve the exact old bytes before --force replaces any result.
        with backup.open("xb") as target:
            target.write(path.read_bytes())
    result = {"schema": "rag-v2-run/1", "metadata": campaign_manifest(cases, base_url, engine),
              "records": [], "journal": []}
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
    result = prepare_run(path, cases, args.base_url, args.force, engine=args.engine)
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
                row.update({k: result["metadata"][k] for k in ("campaign_id", "engine", "cases_sha256")})
                row["attempt_index"] = 1 + max((r.get("attempt_index", 1) for r in result.get("journal", [])
                    if (r["case_id"], r["repeat"]) == (row["case_id"], row["repeat"])), default=0)
                result.setdefault("journal", []).append(dict(row))
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


percentile = scoring.percentile
ratio = scoring.ratio
infra_error = scoring.infra_error
error_label = scoring.error_label


_CHUNK_TEXT: dict[str, str] = {}


def corpus_texts():
    if not _CHUNK_TEXT and CORPUS.exists():
        for row in read_jsonl(CORPUS):
            _CHUNK_TEXT[row["chunk_id"]] = " ".join(row.get("text", row.get("content_text", "")).split())
    return _CHUNK_TEXT


def cites_gold(case, cited_ids):
    return scoring.cites_gold(case, cited_ids, corpus_texts())


def metrics(rows, cases):
    return scoring.metrics(rows, cases, corpus_texts())


def score_records(records, cases, split="holdout", *, strict=False, manifests=(), journal=(), chunk_text=None):
    selected = {c["case_id"]: c for c in cases if split == "all" or c["split"] == split}
    if not selected or len({c["case_id"] for c in cases}) != len(cases):
        raise ValueError("Empty selection or duplicate case IDs")
    if {r["case_id"] for r in records} - {c["case_id"] for c in cases}:
        raise ValueError("Results contain unknown case IDs")
    rows = [r for r in records if r["case_id"] in selected]
    seen = set()
    for r in rows:
        key = (r.get("source_run"), r["case_id"], r.get("repeat", 1))
        seen.add(key)
        if r.get("outcome_class") not in ANSWERED | {"refuse", "clarify", "error"}:
            raise ValueError("Invalid outcome_class")
    issues = scoring.record_issues(rows, list(selected.values()))
    issues += scoring.campaign_issues(manifests, rows, list(selected.values()))
    if strict and issues:
        raise ValueError("Invalid campaign coverage/provenance")
    texts = corpus_texts() if chunk_text is None else chunk_text
    report = {"schema": "rag-v2-score/1", "split": split,
              "metrics": scoring.metrics(rows, selected, texts),
              "by_family": {}, "by_variant": {}, "case_outcomes": {},
              "provenance": {"issues": sorted(set(issues)), "manifests": list(manifests),
                             "cases_sha256": fingerprint(list(selected.values()))},
              "attempt_metrics": scoring.attempt_metrics(rows, [r for r in journal if r["case_id"] in selected])}
    for field in ("family", "variant"):
        for value in sorted({c[field] for c in selected.values()}):
            subset = [r for r in rows if selected[r["case_id"]][field] == value]
            report["by_" + field][value] = scoring.metrics(subset, selected, texts, confidence=False)
    for cid in sorted(selected):
        report["case_outcomes"][cid] = [
            {"repeat": r.get("repeat", 1), "outcome_class": r["outcome_class"],
             "result_sha256": fingerprint({k: r.get(k) for k in (
                 "outcome_class", "answer_text", "citation_chunk_ids", "error")})}
            for r in sorted(rows, key=lambda r: r.get("repeat", 1)) if r["case_id"] == cid]
    counts = {cid: [r["repeat"] for r in rs] for cid, rs in report["case_outcomes"].items()}
    incomplete = [cid for cid, indices in counts.items() if len(indices) != len(set(indices))
                  or not {1, 2, 3} <= set(indices)]
    report["coverage"] = {"selected_cases": len(selected), "attempts": len(rows),
        "missing_cases": [cid for cid, indices in counts.items() if not indices],
        "fewer_than_three_repeats": incomplete,
        "holdout_three_repeats_complete": split == "holdout" and not incomplete,
        "issues": scoring.record_issues(rows, list(selected.values()))}
    report["distribution"] = {"issues": scoring.distribution_issues(list(selected.values()))}
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


def load_report(path, cases, split, *, strict=False):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") == "rag-v2-score/1":
        if strict and (not data.get("provenance") or data["provenance"].get("issues")):
            raise ValueError("Scored report lacks valid campaign provenance")
        return data
    return score_records(data["records"], cases, split, strict=strict,
                         manifests=[data.get("metadata", {})], journal=data.get("journal", []))


def compare_reports(a, b, *, strict=False):
    if a["split"] != b["split"]:
        raise ValueError("Cannot compare different splits")
    issues = []
    if set(a["case_outcomes"]) != set(b["case_outcomes"]):
        issues.append("different_case_set")
    pa, pb = a.get("provenance", {}), b.get("provenance", {})
    if not pa or not pb or pa.get("issues") or pb.get("issues"):
        issues.append("invalid_campaign")
    ma, mb = pa.get("manifests", []), pb.get("manifests", [])
    issues += scoring.campaign_issues(ma + mb)
    if pa.get("cases_sha256") != pb.get("cases_sha256"):
        issues.append("different_cases_sha256")
    # Exploratory cross-engine/campaign comparison remains available without --strict.
    if strict and issues:
        raise ValueError("Cannot compare incomplete or incompatible campaigns")
    changed = []
    for cid in sorted(set(a["case_outcomes"]) | set(b["case_outcomes"])):
        left, right = a["case_outcomes"].get(cid, []), b["case_outcomes"].get(cid, [])
        if left != right:
            changed.append({"case_id": cid, "a": left, "b": right})
    return {"criteria": {f"A{i}": {"a": a["metrics"][f"A{i}"], "b": b["metrics"][f"A{i}"]}
                         for i in range(1, 10)}, "changed_cases": changed, "warnings": issues}


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
    live.add_argument("--engine", choices=("v1", "v2"), default="v2",
                      help="Declared engine served by this endpoint; persisted in campaign manifest")
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
    for command in ("score", "gate"):
        scoring_parser = sub.add_parser(command)
        scoring_parser.add_argument("--results", action="append", required=True)
        scoring_parser.add_argument("--cases", required=True)
        scoring_parser.add_argument("--split", choices=("dev", "holdout", "all"), default="holdout")
        scoring_parser.add_argument("--strict", action="store_true")
        scoring_parser.add_argument("--out", help="Default: first results filename + .score.json; must not exist")
    comparison = sub.add_parser("compare")
    comparison.add_argument("--a", required=True)
    comparison.add_argument("--b", required=True)
    comparison.add_argument("--cases", default=str(CASES), help="Required for raw result inputs, unused for scored reports")
    comparison.add_argument("--split", choices=("dev", "holdout", "all"), default="holdout")
    comparison.add_argument("--out", help="Optional new comparison JSON")
    comparison.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            run(args)
        elif args.command in {"score", "gate"}:
            inputs = [json.loads(Path(path).read_text(encoding="utf-8")) for path in args.results]
            records = [row | {"source_run": str(Path(path).resolve())} for path, data in zip(args.results, inputs)
                       for row in data["records"]]
            report = score_records(records, read_jsonl(Path(args.cases)), args.split,
                strict=args.strict, manifests=[d.get("metadata", {}) for d in inputs],
                journal=[row for d in inputs for row in d.get("journal", [])])
            output = writable_path(args.out or (args.results[0] + ".score.json"))
            write_json(output, report)
            show_metrics("Overall", report["metrics"])
            for field in ("family", "variant"):
                for key, values in report["by_" + field].items():
                    show_metrics(f"{field}: {key}", values)
            print("Coverage: " + json.dumps(report["coverage"], ensure_ascii=False))
            print("uncited_answer: " + json.dumps(report["metrics"]["uncited_answer"]))
            print("A7 attempts: " + json.dumps(report["attempt_metrics"]))
            if report["provenance"]["issues"]:
                print("WARNING: " + ", ".join(report["provenance"]["issues"]))
            print(f"JSON: {output}")
            if args.command == "gate":
                passed = (not report["provenance"]["issues"] and not report["distribution"]["issues"]
                          and all(report["metrics"][f"A{i}"].get("passed") is True for i in range(1, 9)))
                return 0 if passed else 1
        else:
            inputs = [json.loads(Path(path).read_text(encoding="utf-8")) for path in (args.a, args.b)]
            cases = read_jsonl(Path(args.cases)) if any(data.get("schema") != "rag-v2-score/1" for data in inputs) else []
            a, b = [load_report(path, cases, args.split, strict=args.strict) for path in (args.a, args.b)]
            report = compare_reports(a, b, strict=args.strict)
            print("criterion | v1 (a) | v2 (b)")
            for criterion, pair in report["criteria"].items():
                print(f"{criterion} | {status(pair['a'])} {json.dumps(pair['a'], ensure_ascii=False)} | "
                      f"{status(pair['b'])} {json.dumps(pair['b'], ensure_ascii=False)}")
            print("Changed cases: " + json.dumps(report["changed_cases"], ensure_ascii=False))
            if report["warnings"]:
                print("WARNING: " + ", ".join(report["warnings"]))
            if args.out:
                write_json(writable_path(args.out), report)
    except (ValueError, OSError, KeyError, TypeError, httpx.HTTPError) as error:
        # No exception message here: paths/data/HTTP errors can contain secrets.
        parser.exit(2, f"{type(error).__name__}: invalid input, output conflict, or local runtime failure\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
