"""Staged load test of the chat API: N virtual students ask realistic questions at the same time.

  python evals/runners/rag_load_test.py --stages 10,20,50 --turns 5 --out evals/results/rag-load/<name>.json

Each virtual user shares one local test login (the platform has a single synthetic student), opens a temporary
conversation per question, streams the answer and thinks 0-2 s before the next one. The per-user abuse limiter
(30 requests/min per account) would otherwise cap the whole test at ~15 turns/min, so run the API with the
test-only override in evals/load/README.md (CAMPUS_LOADTEST_NO_RATE_LIMIT=1 through evals/load/sitecustomize.py). Everything below the limiter is the real code path.

A stage is aborted early when more than --abort-error-rate of its turns fail, to protect the paid provider budget.
Reports per stage: turns, error and outcome mix, latency p50/p90/p95/p99, time to first event, throughput, API CPU/RAM.
"""
from __future__ import annotations

import argparse
import asyncio
import codecs
import importlib.util
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("rag_natural_eval", Path(__file__).with_name("rag_natural_eval.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

def question_pool() -> list[str]:
    pool = []
    for name in ("real-style-20261114.jsonl", "natural-cases-20261114.jsonl"):
        for line in (ROOT / "evals/datasets/rag-v2" / name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                case = json.loads(line)
                if case["expected"] == "answer" and not case.get("history"):
                    pool.append(case["question"])
    return pool


async def login(base_url: str) -> httpx.Cookies:
    cred = json.loads(base.CRED.read_text(encoding="utf-8"))
    async with httpx.AsyncClient(base_url=base_url, trust_env=False, timeout=60) as client:
        r = await client.post("/v1/knowledge/platform/session", json={"username": cred["username"], "password": cred["password"]})
        r.raise_for_status()
        return client.cookies


async def one_turn(client: httpx.AsyncClient, question: str) -> dict:
    started = time.perf_counter()
    rec = {"question": question, "seconds": None, "ttfb": None, "outcome": "error", "error": None, "status": None, "retries_429": 0}
    try:
        conv = await client.post("/v1/conversations", json={"mode": "temporary"})
        rec["status"] = conv.status_code
        if conv.status_code == 429:
            rec["retries_429"] += 1
        conv.raise_for_status()
        path = f"/v1/conversations/{conv.json()['id']}/messages:stream"
        buffer, decoder = "", codecs.getincrementaldecoder("utf-8")()
        stream_started = time.perf_counter()
        async with client.stream("POST", path, json={"content": question}) as response:
            rec["status"] = response.status_code
            if response.status_code == 503 and response.headers.get("retry-after"):
                # Admission control refused the turn before it started: nothing was sent, the student may retry.
                # `seconds` is how long the refusal itself took (the stream request), not the conversation setup.
                rec["outcome"], rec["retry_after"] = "busy", int(response.headers["retry-after"])
                rec["seconds"] = round(time.perf_counter() - stream_started, 2)
                return rec
            response.raise_for_status()
            async for raw in response.aiter_bytes():
                if rec["ttfb"] is None:
                    rec["ttfb"] = round(time.perf_counter() - started, 2)
                buffer += decoder.decode(raw).replace("\r\n", "\n")
        final = base.final_of(buffer)
        rec["outcome"] = base.outcome(final)
        text = (final or {}).get("content", "")
        if "chưa kịp xác minh" in text or "hết thời gian" in text:
            rec["outcome"] = "timeout_message"
        if (final or {}).get("response_class") == "system_error":
            rec["outcome"] = "system_error"
    except Exception as exc:  # noqa: BLE001 -- recorded, never raised
        rec["error"] = type(exc).__name__
    rec["seconds"] = round(time.perf_counter() - started, 2)
    return rec


async def virtual_user(index: int, cookies, base_url: str, questions: list[str], turns: int, rng: random.Random, sink: list,
                       think: tuple[float, float] = (0.0, 2.0), busy_retries: int = 3, pick=None):
    async with httpx.AsyncClient(base_url=base_url, trust_env=False, timeout=120, cookies=cookies) as client:
        await asyncio.sleep(rng.uniform(0, max(3.0, think[1])))  # arrivals are spread out, not simultaneous
        for _ in range(turns):
            question, refusals = (pick() if pick else rng.choice(questions)), []
            for _attempt in range(busy_retries + 1):
                rec = await one_turn(client, question)
                if rec["outcome"] != "busy":
                    break
                refusals.append(rec["seconds"])  # a student who is told "busy" waits a moment and asks again
                await asyncio.sleep(rec.get("retry_after", 5))
            else:
                rec["outcome"] = "gave_up_busy"
            rec["busy_refusals"] = refusals
            sink.append(rec)
            await asyncio.sleep(rng.uniform(*think))


def percentile(values: list[float], p: float):
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * p))] if values else None


PS_SAMPLE = (
    "Get-CimInstance Win32_PerfFormattedData_PerfProc_Process | Where-Object { $_.IDProcess -in (%s) } | "
    "ForEach-Object { '{0},{1}' -f $_.PercentProcessorTime, [int]($_.WorkingSet/1MB) }")


def api_pids(port: int) -> list[int]:
    import subprocess
    # The serving process and, with several API workers, the worker processes it started.
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
        "$all = Get-CimInstance Win32_Process; "
        "$parents = @($all | Where-Object { $_.CommandLine -match 'knowledge_platform.py serve' -and "
        f"$_.CommandLine -match '--port {port}' }} | ForEach-Object {{ $_.ProcessId }}); "
        "$all | Where-Object { $parents -contains $_.ProcessId -or $parents -contains $_.ParentProcessId } | "
        "ForEach-Object { $_.ProcessId }"], capture_output=True, text=True).stdout
    return [int(x) for x in out.split() if x.isdigit()]


async def sample_resources(stop: asyncio.Event, out: list, port: int):
    """API CPU % (of one core) and memory, sampled every ~4 s through Windows performance counters."""
    import subprocess
    pids = api_pids(port)
    if not pids:
        return
    command = PS_SAMPLE % ",".join(map(str, pids))
    while not stop.is_set():
        await asyncio.sleep(3)
        result = await asyncio.to_thread(lambda: subprocess.run(["powershell", "-NoProfile", "-Command", command],
                                                                 capture_output=True, text=True).stdout)
        rows = [tuple(map(int, line.split(","))) for line in result.split() if line.count(",") == 1]
        if rows:
            out.append({"cpu": sum(r[0] for r in rows), "rss_mb": max(r[1] for r in rows)})


async def run_stage(users: int, turns: int, base_url: str, abort_rate: float, seed: int, think: tuple[float, float] = (0.0, 2.0),
                    busy_retries: int = 3, unique: bool = False) -> dict:
    cookies = await login(base_url)
    questions = question_pool()
    rng = random.Random(seed + users)
    pick = None
    if unique:
        # No question twice in the stage: nothing can be answered from a repeat (query-vector cache, answer reuse).
        if users * turns > len(questions):
            raise SystemExit(f"--unique-questions needs at most {len(questions)} turns in a stage, got {users * turns}")
        shuffled = list(questions)
        rng.shuffle(shuffled)
        queue = iter(shuffled)
        pick = lambda: next(queue)  # noqa: E731
    sink, samples, stop = [], [], asyncio.Event()
    sampler = asyncio.create_task(sample_resources(stop, samples, int(base_url.rsplit(":", 1)[1])))
    started = time.perf_counter()
    tasks = [asyncio.create_task(virtual_user(i, cookies, base_url, questions, turns, random.Random(seed + users * 100 + i), sink, think, busy_retries, pick))
             for i in range(users)]

    async def watchdog():
        while not all(t.done() for t in tasks):
            await asyncio.sleep(5)
            done = len(sink)
            if done >= 20 and sum(r["outcome"] in {"error", "timeout_message", "system_error"} for r in sink) / done > abort_rate:
                for t in tasks:
                    t.cancel()
                return True
        return False

    aborted = await watchdog()
    await asyncio.gather(*tasks, return_exceptions=True)
    stop.set()
    await sampler
    wall = time.perf_counter() - started
    served = [r for r in sink if r["outcome"] != "gave_up_busy"]  # latency of turns that actually ran
    secs = [r["seconds"] for r in served if r["seconds"] is not None]
    ok = [r for r in sink if r["outcome"] in {"answer", "partial", "clarify", "refuse"}]
    refusals = [s for r in sink for s in r.get("busy_refusals", [])] + [r["seconds"] for r in sink if r["outcome"] == "gave_up_busy"]
    return {
        "users": users, "think_s": list(think), "turns_done": len(sink), "turns_planned": users * turns, "aborted_for_errors": aborted,
        "wall_seconds": round(wall, 1), "turns_per_minute": round(len(sink) / wall * 60, 1),
        "outcomes": dict(Counter(r["outcome"] for r in sink)),
        "failed_questions": [{"question": r["question"], "outcome": r["outcome"], "seconds": r["seconds"]} for r in sink
                             if r["outcome"] in {"error", "timeout_message", "system_error"}],
        "busy": {"refusals": len(refusals), "turns_refused_at_least_once": sum(bool(r.get("busy_refusals")) for r in sink),
                 "gave_up": sum(r["outcome"] == "gave_up_busy" for r in sink),
                 "refusal_seconds_max": max(refusals, default=None)},
        "http_status": dict(Counter(r["status"] for r in sink)),
        "exceptions": dict(Counter(r["error"] for r in sink if r["error"])),
        "success_rate": round(len(ok) / len(sink), 3) if sink else None,
        "latency_s": {k: percentile(secs, p) for k, p in (("p50", .5), ("p90", .9), ("p95", .95), ("p99", .99))} | {"max": max(secs, default=None)},
        "ttfb_p50_s": percentile([r["ttfb"] for r in sink if r["ttfb"] is not None], .5),
        "api_cpu_percent_p50_p95": [percentile([s["cpu"] for s in samples], .5), percentile([s["cpu"] for s in samples], .95)] if samples else None,
        "api_rss_mb_max": max((s["rss_mb"] for s in samples), default=None),
    }


async def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stages", default="10,20,50")
    parser.add_argument("--turns", type=int, default=5)
    parser.add_argument("--base-url", default="http://127.0.0.1:8015")
    parser.add_argument("--abort-error-rate", type=float, default=0.30)
    parser.add_argument("--pause", type=int, default=20, help="seconds between stages")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--think-min", type=float, default=0.0, help="seconds a user pauses after an answer (realistic: 8-25)")
    parser.add_argument("--think-max", type=float, default=2.0)
    parser.add_argument("--busy-retries", type=int, default=3,
                        help="how many times a student asks again after a 503 'busy' (waiting Retry-After seconds)")
    parser.add_argument("--unique-questions", action="store_true",
                        help="draw questions without replacement, so no turn repeats an earlier question of the stage")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    results = []
    for n in [int(x) for x in args.stages.split(",")]:
        print(f"--- stage: {n} concurrent users x {args.turns} questions", flush=True)
        result = await run_stage(n, args.turns, args.base_url, args.abort_error_rate, args.seed, (args.think_min, args.think_max),
                                  args.busy_retries, args.unique_questions)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        if result["aborted_for_errors"]:
            print("stage aborted for errors: stopping the ramp to protect the provider budget", flush=True)
            break
        await asyncio.sleep(args.pause)


if __name__ == "__main__":
    asyncio.run(main())
