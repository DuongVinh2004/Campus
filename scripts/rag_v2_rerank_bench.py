"""Measure the actual local reranker using only approved corpus passages.

Run with .venv/Scripts/python.exe -B scripts/rag_v2_rerank_bench.py.
Results contain timings/counts/hashes only; an existing output is never replaced.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api/src"))

from campus247.rag_v2.adapters.http_reranker import HTTPReranker


async def measure(corpus: Path, *, repeats: int, deadline_s: float, concurrency: int) -> dict:
    passages = []
    with corpus.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            text = row.get("text", row.get("content_text", ""))
            if len(text) >= 600:
                passages.append(text)
            if len(passages) == 12:
                break
    if len(passages) < 12:
        raise ValueError("benchmark requires 12 corpus passages of at least 600 characters")
    query = passages[0].splitlines()[0][:150] or passages[0][:150]
    reranker = HTTPReranker(batch_size=4 if concurrency > 1 else 12, concurrency=concurrency)
    rows = []
    for chars in (300, 600):
        for pairs in (4, 8, 12):
            durations, failures = [], []
            for _ in range(repeats):
                started = perf_counter()
                try:
                    scores = await reranker.rerank(query, [p[:chars] for p in passages[:pairs]], deadline_s=deadline_s)
                    if len(scores) != pairs:
                        raise ValueError("invalid output count")
                    durations.append(perf_counter() - started)
                except Exception as error:  # noqa: BLE001 -- retain failed runs in benchmark evidence
                    failures.append({"code": "TIMEOUT" if isinstance(error, TimeoutError) else "RUNTIME_ERROR",
                                     "elapsed_s": round(perf_counter() - started, 6)})
            median = statistics.median(durations) if durations else None
            rows.append({"pairs": pairs, "text_chars": chars, "successful_runs": len(durations),
                         "durations_s": [round(d, 6) for d in durations],
                         "median_s": round(median, 6) if median is not None else None,
                         "pairs_per_second": round(pairs / median, 6) if median else None,
                         "failures": failures})
    digest = hashlib.sha256()
    with corpus.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"recorded_at": datetime.now(UTC).isoformat(), "corpus_sha256": digest.hexdigest(),
            "endpoint": "127.0.0.1:18082", "includes_info_and_http": True, "warmup_runs": 0,
            "repeats": repeats, "deadline_s": deadline_s, "requested_concurrency": concurrency, "measurements": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "evals/corpus/served-chunks.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "evals/results/rag-judge-20261028/rerank-bench.json")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--deadline-s", type=float, default=45)
    parser.add_argument("--concurrency", type=int, default=1)
    args = parser.parse_args()
    if args.repeats < 1 or args.deadline_s <= 0 or args.concurrency < 1:
        parser.error("positive repeats, deadline and concurrency required")
    output = args.output.resolve()
    if not output.is_relative_to(ROOT) or output == ROOT or output.exists():
        parser.error("output must be a new file inside this workspace")
    # Check each ancestor before writing, including Windows junctions.
    for parent in args.output.absolute().parents:
        if parent.is_symlink() or parent.is_junction():
            parser.error("output cannot traverse a link or junction")
        if parent == ROOT:
            break
    if not output.parent.is_dir():
        parser.error("output parent directory must already exist")
    result = asyncio.run(measure(args.corpus, repeats=args.repeats, deadline_s=args.deadline_s,
                                 concurrency=args.concurrency))
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    for row in result["measurements"]:
        print(f"pairs={row['pairs']} chars={row['text_chars']} median_s={row['median_s']} pairs/s={row['pairs_per_second']} failures={len(row['failures'])}")
    return 0 if all(row["successful_runs"] == args.repeats for row in result["measurements"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
