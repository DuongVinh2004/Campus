"""Probe the local runtime with a gold dataset and report disposition plus the retrieval funnel.

Calls the real local API on 127.0.0.1:8015 (it spends the configured generation provider's
budget, one conversation per case). Reads the retained owner credentials locally and never
prints them or the answers. The funnel comes from the API log's `retrieval_pool` and
`retrieval_trace` warning lines, which carry only counts, section labels and scores.

Run from the repository root:
    .venv/Scripts/python.exe -B evals/runners/live_retrieval_probe.py \
        --dataset evals/datasets/natural-questions-gold-20261028.json --out <result.json> [--repeat 2]
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "infra/local/knowledge-platform-20261023"
API = "/v1/knowledge/platform"


def latest_api_log() -> Path:
    logs = sorted(STATE.glob("resume-*/api.log"), key=os.path.getmtime)
    if not logs:
        raise SystemExit("No retained api.log; start the runtime first")
    return logs[-1]


def final_event(stream: str):
    for block in stream.split("\n\n"):
        if "event: message.completed\n" in block:
            return json.loads(next(line[6:] for line in block.splitlines() if line.startswith("data: ")))
    return None


def parse_pool(line: str):
    match = re.match(r"lexical=(\[.*?\]) semantic=(\[.*?\]) chosen=(\[.*?\])\s*$", line.strip())
    return [ast.literal_eval(match[i]) for i in (1, 2, 3)] if match else None


def parse_trace(line: str):
    match = re.search(r"lexical=(\d+) semantic=(\d+) chosen=(\d+) ranked=(\d+) top=(.*)$", line)
    return ast.literal_eval(match[5]) if match else None


def disposition(final) -> str:
    if final is None:
        return "no_final"
    if final.get("status") == "answered":
        return final.get("response_class") or "answered"
    return "clarification" if final.get("response_class") == "clarification_request" else "abstained"


def hit(labels, gold) -> bool:
    return any(any(g in label for g in gold) for label in labels)


def send(client, path: str, payload: dict):
    """POST with the server's own rate-limit hint; the probe must not fail on 429."""
    for _ in range(6):
        response = client.post(path, json=payload)
        if response.status_code != 429:
            return response
        time.sleep(min(60, int(response.headers.get("Retry-After", "5"))) + 0.3)
    return response


def run_case(client, log: Path, case: dict) -> dict:
    offset = log.stat().st_size
    started = time.perf_counter()
    record = {"case_id": case["case_id"], "topic": case.get("topic"), "form": case.get("form")}
    try:
        conv = send(client, "/v1/conversations", {"mode": "temporary"})
        conv.raise_for_status()
        reply = send(client, f"/v1/conversations/{conv.json()['id']}/messages:stream", {"content": case["question"]})
        final = final_event(reply.text)
        record.update(http=reply.status_code, disposition=disposition(final),
                      citation_sections=[(c.get("citation") or {}).get("locator", "") for c in (final or {}).get("citations") or []
                                         if isinstance(c, dict)] if final else [])
    except Exception as error:  # noqa: BLE001 - record only the type, never request content
        record.update(disposition="error", error=type(error).__name__)
    record["seconds"] = round(time.perf_counter() - started, 1)
    time.sleep(0.5)
    new = log.read_bytes()[offset:].decode("utf-8", "ignore")
    pool = [parse_pool(line.split("retrieval_pool ", 1)[1]) for line in new.splitlines() if "retrieval_pool" in line]
    trace = [parse_trace(line) for line in new.splitlines() if "retrieval_trace" in line]
    gold = case.get("gold_section_labels")
    if gold and pool and pool[-1]:
        lexical, semantic, chosen = pool[-1]
        record.update(in_pool=hit(lexical + semantic, gold), in_chosen=hit(chosen, gold))
    if pool and pool[-1]:
        record["chosen_count"] = len(pool[-1][2])
    if trace and trace[-1]:
        # Section labels and raw reranker logits only; no question or passage text.
        record["rerank_top"] = trace[-1]
        record["best_score"] = max(score for _, score in trace[-1])
        if gold:
            record["in_top_positive"] = hit([p for p, s in trace[-1] if s > 0], gold)
            gold_scores = [s for p, s in trace[-1] if hit([p], gold)]
            record["gold_best_score"] = max(gold_scores) if gold_scores else None
        record["rerank_scored"] = True
    elif pool:
        record["rerank_scored"] = False
    if "kind" in case:
        record["kind"] = case["kind"]
    return record


def summarize(records):
    by_form = defaultdict(Counter)
    for r in records:
        by_form[r.get("form") or r.get("kind", "unlabelled")][r["disposition"]] += 1
    funnel = Counter()
    measured = [r for r in records if "in_pool" in r]
    for key in ("in_pool", "in_chosen", "in_top_positive"):
        funnel[key] = sum(1 for r in measured if r.get(key))
    seconds = [r["seconds"] for r in records if r.get("seconds")]
    return {"cases": len(records), "with_funnel": len(measured), "funnel_hits": dict(funnel),
            "rerank_failed": sum(1 for r in records if r.get("rerank_scored") is False),
            "disposition_by_form": {k: dict(v) for k, v in by_form.items()},
            "seconds_median": statistics.median(seconds) if seconds else None, "seconds_max": max(seconds, default=None)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--api-log")
    args = parser.parse_args()
    cases = json.loads(Path(args.dataset).read_text(encoding="utf-8"))["cases"]
    log = Path(args.api_log) if args.api_log else latest_api_log()
    credentials = json.loads((STATE / "owner-credentials.json").read_text(encoding="utf-8"))
    with httpx.Client(base_url="http://127.0.0.1:8015", trust_env=False, timeout=120) as client:
        login = client.post(API + "/session", json={k: credentials[k] for k in ("username", "password")})
        if login.status_code != 200:
            raise SystemExit(f"Login failed: HTTP {login.status_code}")
        records = [run_case(client, log, case) | {"repeat": n} for n in range(args.repeat) for case in cases]
    result = {"dataset": args.dataset, "summary": summarize(records), "records": records}
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
