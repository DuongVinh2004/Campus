"""Run natural, messy student questions through the live chat API and score helpfulness and safety.

Cases come from ``evals/datasets/rag-v2/natural-cases-*.jsonl`` (derived from machine-verified seeds, so the
required facts are checked by code against the answer text). The runner logs in as the local test student, one
temporary conversation per question, and appends one JSON line per question; resume skips finished ones.

  python evals/runners/rag_natural_eval.py run --cases <jsonl> --out <jsonl> [--limit N] [--concurrency 2]
  python evals/runners/rag_natural_eval.py score --results <jsonl> --cases <jsonl>

Scoring (per style and overall):
  helpful      expected=answer  -> answered/partial AND every required fact present, no forbidden fact
  guided       expected=answer  -> not helpful but not a dead end: a clarification that names the missing scope
  dead_end     expected=answer  -> refused ("chưa đủ căn cứ") or generic unclear prompt
  wrong        any case         -> forbidden fact present, or an answer to an out-of-scope/abstain case
  correct_stop expected=abstain/clarify -> refusal or clarification (never an answer)
"""
from __future__ import annotations

import argparse
import codecs
import importlib.util
import json
import os
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent import futures
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("rag_v2_scoring", Path(__file__).with_name("rag_v2_scoring.py"))
scoring = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scoring)
CRED = ROOT / "infra/local/knowledge-platform-20261023/student-credentials.json"
ANSWERED = {"answer", "partial"}


def final_of(stream_blocks: str):
    for block in stream_blocks.split("\n\n"):
        if "event: message.completed" in block:
            data = [line[5:].lstrip() for line in block.splitlines() if line.startswith("data:")]
            return json.loads("\n".join(data))
    return None


def outcome(final) -> str:
    if not final:
        return "error"
    kind = final.get("outcome_kind")
    if kind in ANSWERED | {"clarify", "refuse"}:
        return kind
    if final.get("response_class") == "system_error":
        return "error"
    if final.get("response_class") == "partial_answer":
        return "partial"
    if final.get("response_class") == "clarification_request":
        return "clarify"
    return "answer" if final.get("status") == "answered" else "refuse"


class Runner:
    # The API allows 30 requests a minute per account on /v1/conversations. A client that goes faster is told to wait
    # (429, Retry-After up to 60 s) and that waiting is not the system's latency. Stay under the limit and do not count
    # the pacing wait in the measured seconds, so p90 reflects the answer time, not the harness running too fast.
    PACE_LIMIT, PACE_WINDOW_S = 27, 60.0

    def __init__(self, base, concurrency):
        self.base, self.lock = base, threading.Lock()
        self.pool = futures.ThreadPoolExecutor(max_workers=concurrency)
        self._sent, self._pace_lock = [], threading.Lock()

    def pace(self) -> float:
        """Block until one more request fits in the window; return the seconds waited."""
        waited = 0.0
        while True:
            with self._pace_lock:
                now = time.monotonic()
                self._sent = [t for t in self._sent if now - t < self.PACE_WINDOW_S]
                if len(self._sent) < self.PACE_LIMIT:
                    self._sent.append(now)
                    return waited
                delay = self.PACE_WINDOW_S - (now - self._sent[0]) + 0.05
            time.sleep(delay)
            waited += delay

    def client(self):
        cred = json.loads(CRED.read_text(encoding="utf-8"))
        # EVAL_CA_BUNDLE: trust this CA file (for a TLS-terminating proxy with a private CA, such as the cloud kit rehearsal).
        client = httpx.Client(base_url=self.base, trust_env=False, timeout=120, verify=os.environ.get("EVAL_CA_BUNDLE") or True)
        r = client.post("/v1/knowledge/platform/session", json={"username": cred["username"], "password": cred["password"]})
        r.raise_for_status()
        return client

    def ask(self, client, question, history=()):
        started = time.perf_counter()
        paced = 0.0
        record = {"seconds": None, "outcome": "error", "content": "", "citations": 0, "error": None}
        try:
            conversation = None
            for _ in range(6):
                paced += self.pace()
                conversation = client.post("/v1/conversations", json={"mode": "temporary"})
                if conversation.status_code != 429:
                    break
                wait = int(conversation.headers.get("Retry-After", "5")) + 0.3
                time.sleep(wait)
                paced += wait  # told to wait by the per-account limiter: not answer time
            conversation.raise_for_status()
            path = f"/v1/conversations/{conversation.json()['id']}/messages:stream"
            final = None
            for turn in (*history, question):
                final = None
                for _ in range(6):
                    paced += self.pace()
                    with client.stream("POST", path, json={"content": turn}) as response:
                        if response.status_code == 429:
                            wait = int(response.headers.get("Retry-After", "5")) + 0.3
                            time.sleep(wait)
                            paced += wait
                            continue
                        response.raise_for_status()
                        decoder, buffer = codecs.getincrementaldecoder("utf-8")(), ""
                        for raw in response.iter_bytes():
                            buffer += decoder.decode(raw).replace("\r\n", "\n")
                        final = final_of(buffer)
                        break
            record.update(outcome=outcome(final), content=(final or {}).get("content", ""),
                          citations=len((final or {}).get("citations") or []),
                          response_class=(final or {}).get("response_class"))
        except Exception as exc:  # noqa: BLE001 -- recorded, never raised
            record["error"] = type(exc).__name__
        record["seconds"] = round(time.perf_counter() - started - paced, 1)
        return record


def run(args):
    cases = [json.loads(l) for l in Path(args.cases).read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.style:
        cases = [c for c in cases if c.get("style") in args.style.split(",")]
    if args.limit:
        cases = cases[:args.limit]
    out = Path(args.out)
    done = set()
    if out.exists():
        done = {json.loads(l)["case_id"] for l in out.read_text(encoding="utf-8").splitlines() if l.strip()}
    todo = [c for c in cases if c["case_id"] not in done]
    runner = Runner(args.base_url, args.concurrency)
    clients = [runner.client() for _ in range(args.concurrency)]
    lock = threading.Lock()

    def work(index_case):
        index, case = index_case
        record = runner.ask(clients[index % len(clients)], case["question"], case.get("history", ()))
        record.update(case_id=case["case_id"], style=case.get("style"), expected=case["expected"], question=case["question"])
        with lock:
            with out.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    with futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for n, record in enumerate(pool.map(work, enumerate(todo)), 1):
            print(f"{n}/{len(todo)} {record['case_id']} {record['style']} -> {record['outcome']} {record['seconds']}s", flush=True)


def judge(case, row):
    text = row.get("content", "")
    kind = row["outcome"]
    forbidden = any(scoring.fact_matches(f, text) for f in case.get("forbidden_facts", []))
    if kind == "error":
        return "error"
    if case["expected"] == "answer":
        if forbidden:
            return "wrong"
        if kind in ANSWERED and all(scoring.fact_matches(f, text) for f in case.get("required_facts", [])):
            return "helpful"
        if kind in ANSWERED:
            return "incomplete"
        if kind == "clarify" and "chưa rõ nội dung" not in text:
            return "guided"
        return "dead_end"
    if kind in ANSWERED:
        return "wrong"
    return "correct_stop"


def score(args):
    cases = {}
    for l in Path(args.cases).read_text(encoding="utf-8").splitlines():
        if l.strip():
            c = json.loads(l)
            cases[c["case_id"]] = c
    rows = [json.loads(l) for l in Path(args.results).read_text(encoding="utf-8").splitlines() if l.strip()]
    by_style = defaultdict(Counter)
    for row in rows:
        verdict = judge(cases[row["case_id"]], row)
        row["verdict"] = verdict
        by_style[row.get("style") or "?"][verdict] += 1
        by_style["ALL"][verdict] += 1
    for style, counter in sorted(by_style.items()):
        total = sum(counter.values())
        print(f"{style:10} n={total:3} " + " ".join(f"{k}={counter[k]}({counter[k] / total:.0%})" for k in
              ("helpful", "incomplete", "guided", "dead_end", "wrong", "correct_stop", "error") if counter[k]))
    secs = sorted(r["seconds"] for r in rows if r.get("seconds"))
    if secs:
        print(f"latency p50={secs[len(secs) // 2]}s p90={secs[int(len(secs) * .9)]}s")
    if args.show:
        for row in rows:
            if row["verdict"] in args.show.split(","):
                print(f"\n[{row['verdict']}] {row['case_id']} {row['style']} :: {row['question'][:160]}\n   -> {row['outcome']} :: {row['content'][:240].replace(chr(10), ' | ')}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run")
    r.add_argument("--cases", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--base-url", default="http://127.0.0.1:8015")
    r.add_argument("--limit", type=int)
    r.add_argument("--style")
    r.add_argument("--concurrency", type=int, default=2)
    s = sub.add_parser("score")
    s.add_argument("--results", required=True)
    s.add_argument("--cases", required=True)
    s.add_argument("--show", help="comma list of verdicts to print")
    args = parser.parse_args()
    run(args) if args.command == "run" else score(args)


if __name__ == "__main__":
    main()
