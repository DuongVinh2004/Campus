"""F7 hint safety with the real provider: does a model-written level 1-2 hint pass the code checks, and does anything shown leak?

  infra/local/rag-fixture/.venv/Scripts/python.exe -B evals/runners/tutor_hint_eval.py [--questions 100] [--max-calls 420] [--out DIR]

Cases are machine-made and their gold is checked by code: 100 fill-in-the-number questions built from sentences of the
public HUCE regulation and curriculum text in the RAG v2 index (one question per passage, at most 30 per document, fixed seed).
The blank's number is the correct option; three other numbers of the same passage (or nearby values) are distractors. Each
question gets a level 1 and a level 2 hint from the same `LearningTutor.model_hint` the API uses, through the gateway sidecar
(the paid ledger, the 5 s bound and the 28,000-byte bound are the sidecar's, unchanged). The run stops at --max-calls.

Reported: first-attempt pass rate (target >= 80 %), hints shown by the model vs replaced by the template, and an independent
re-check of every shown hint (the correct number as a whole word in hint or quote = leak; quote not verbatim on the page = fail).
Real students are not involved; whether hints help learning is unmeasured.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "data/rag_v2_vendor"), str(ROOT / "services/api/src")]

from campus247.application.learning.tutor import LearningTutor  # noqa: E402
from campus247.domain.learning.tutor_hints import fold, hint_issues, leaks  # noqa: E402
from campus247.infrastructure.llm.remote_gateway import RemoteGateway, read_token  # noqa: E402
from campus247.rag_v2.adapters.index_store import read_index  # noqa: E402
from campus247.rag_v2.ingest.units import source_text  # noqa: E402

INDEX = ROOT / "data/rag_v2_index/embedded2"
TOKEN = ROOT / "infra/local/public-rag-20261013/gateway-sidecar.token"
NUMBER = re.compile(r"(?<![\d.,/])(\d{1,3})(?![\d.,/])\s*(tín chỉ|TC|%|tuần|ngày|tháng|năm|học kỳ|điểm|lần|tiết|giờ|phút|môn|học phần|sinh viên|người|bản|trang)\b", re.IGNORECASE)
SEED = 20261126


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?;])\s+|\n+", text) if 30 <= len(s.strip()) <= 300]


def build(n: int) -> list[dict]:
    snapshot = read_index(INDEX)
    rng = random.Random(SEED)
    units = sorted(snapshot.units, key=lambda u: u.unit_id)
    rng.shuffle(units)
    cases, per_doc, seen_pages = [], Counter(), set()
    for unit in units:
        if per_doc[unit.doc_title] >= 30:            # spread the cases over documents
            continue
        page = source_text(unit)
        if not 300 <= len(page) <= 6000 or page in seen_pages:
            continue
        candidates = [s for s in sentences(page) if len(NUMBER.findall(s)) == 1]
        others = [s for s in sentences(page) if not NUMBER.search(s)]
        if not candidates or len(others) < 2:
            continue
        sentence = rng.choice(candidates)
        match = NUMBER.search(sentence)
        value, unit_word = match.group(1), match.group(2)
        numbers = sorted({m.group(1) for m in NUMBER.finditer(page)} - {value})
        distractors = numbers[:3]
        step = max(1, int(value) // 5)
        k = 1
        while len(distractors) < 3:                  # nearby values, each one new
            guess = str(int(value) + step * k)
            k += 1
            if guess not in distractors and guess != value:
                distractors.append(guess)
        options = [value] + distractors[:3]
        rng.shuffle(options)
        blank = sentence[:match.start(1)] + "____" + sentence[match.end(1):]
        assert sentence in page and value in sentence                                    # gold checked by code
        cases.append({"id": hashlib.sha256((unit.unit_id + sentence).encode()).hexdigest()[:12], "doc": unit.doc_title,
                      "prompt": f"Điền số còn thiếu ({unit_word}): {blank}", "options": options, "answer": value, "page_text": page})
        per_doc[unit.doc_title] += 1
        seen_pages.add(page)
        if len(cases) == n:
            break
    return cases


def score(rows: list[dict], n_cases: int, provider_calls: int) -> dict:
    done = [r for r in rows if "skipped" not in r]
    # A page the egress policy refuses (a contact or an ID-like number on it) never reaches the provider: the template is shown.
    refused = [r for r in done if r["attempts"][:1] == [["EGRESS_DENIED"]]]
    sent = [r for r in done if r["attempts"][:1] != [["EGRESS_DENIED"]]]
    first_pass = sum(1 for r in sent if r["attempts"] and r["attempts"][0] == ["OK"])
    shown = [r for r in done if r["origin"] == "MODEL"]
    reasons = Counter(code for r in done for attempt in r["attempts"] for code in attempt if code != "OK")
    return {
        "cases": n_cases, "hint_requests": len(done), "skipped": len(rows) - len(done), "provider_calls": provider_calls,
        "refused_by_egress_policy": len(refused), "sent_to_provider": len(sent),
        "first_attempt_pass_rate": round(first_pass / len(sent), 3) if sent else None,
        "shown_from_model": len(shown), "replaced_by_template": len(done) - len(shown),
        "shown_with_leak": sum(1 for r in shown if r["leak"] or r["leak_by_filter_rule"]),
        "shown_quote_not_verbatim": sum(1 for r in shown if not r["quote_verbatim"]),
        "shown_failing_recheck": sum(1 for r in shown if r["recheck_issues"]),
        "rejection_reasons": dict(reasons.most_common()),
        "p90_seconds": sorted(r["seconds"] for r in done)[max(0, int(len(done) * 0.9) - 1)] if done else None,
        "evidence": "machine-made fill-in-the-number cases from the RAG v2 index, gold checked by code; real provider via the sidecar",
    }


class Probe(LearningTutor):
    def __init__(self, gateway):
        self.ai_gateway = gateway


async def run(args) -> dict:
    cases = build(args.questions)
    gateway = RemoteGateway("http://127.0.0.1:8025", read_token(TOKEN))
    probe = Probe(gateway)
    calls = {"n": 0}
    semaphore = asyncio.Semaphore(args.concurrency)
    rows = []

    async def one(case, level):
        async with semaphore:
            if calls["n"] + 2 > args.max_calls:
                return {"case": case["id"], "level": level, "skipped": "MAX_CALLS"}
            trace: list[list[str]] = []
            started = time.monotonic()
            context = {"prompt": case["prompt"], "options": case["options"], "explanation": ""}
            shown = await probe.model_hint(context, [case["answer"]], [], case["page_text"], 1, level, [], None, trace=trace)
            calls["n"] += sum(1 for attempt in trace if attempt != ["EGRESS_DENIED"])
            row = {"case": case["id"], "level": level, "attempts": trace, "seconds": round(time.monotonic() - started, 2),
                   "origin": "MODEL" if shown else "TEMPLATE"}
            if shown:
                # Independent re-check of what would be shown (not the same call path as the filter's own decision).
                # The number between non-digits anywhere in hint or quote, after dropping "trang 1" (the page the hint points to).
                # Independent of the filter's code: every number of the text by value, after dropping "trang 1" (the page pointer).
                shown_text = re.sub(r"(?i)\btrang\s+1(?!\d)", " ", shown["hint"] + " " + shown["quote"])
                numbers = {int(re.sub(r"[.,]", "", n)) for n in re.findall(r"\d+(?:[.,]\d+)*", shown_text) if len(n) < 12}
                row["leak"] = int(case["answer"]) in numbers
                row["leak_by_filter_rule"] = leaks(shown["hint"] + " " + shown["quote"], [case["answer"]], page_no=1)
                # Word for word on the page; runs of spaces and line breaks count as one (the page text keeps PDF line breaks).
                row["quote_verbatim"] = len(shown["quote"]) >= 12 and re.sub(r"\s+", " ", shown["quote"]).strip() in re.sub(r"\s+", " ", case["page_text"])
                row["quote_exact"] = shown["quote"] in case["page_text"]
                row["recheck_issues"] = hint_issues(shown["hint"], shown["quote"], case["page_text"], level=level,
                                                    correct_answers=[case["answer"]], page_no=1)
                row["hint"], row["quote"] = shown["hint"], shown["quote"]
            return row

    rows = await asyncio.gather(*(one(case, level) for case in cases for level in (1, 2)))
    report = score(rows, len(cases), calls["n"])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "cases.jsonl").write_text("\n".join(json.dumps({k: v for k, v in c.items() if k != "page_text"} | {"page_sha256": hashlib.sha256(c["page_text"].encode()).hexdigest()}, ensure_ascii=False) for c in cases) + "\n", encoding="utf-8")
    (out / "rows.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--questions", type=int, default=100)
    parser.add_argument("--max-calls", type=int, default=420)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--out", default=str(ROOT / "evals/results/tutor-20261126"))
    parser.add_argument("--dry-run", action="store_true", help="build and print the cases only, no provider call")
    parser.add_argument("--rescore", action="store_true", help="recompute report.json from rows.jsonl, no provider call")
    args = parser.parse_args()
    if args.rescore:
        out = Path(args.out)
        rows = [json.loads(line) for line in (out / "rows.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        old = json.loads((out / "report.json").read_text(encoding="utf-8"))
        report = score(rows, old["cases"], old["provider_calls"])
        (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    if args.dry_run:
        cases = build(args.questions)
        print(len(cases), "cases;", json.dumps({k: v for k, v in cases[0].items() if k != "page_text"}, ensure_ascii=False))
        return
    print(json.dumps(asyncio.run(run(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
