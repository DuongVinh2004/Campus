"""Semantic scoring for natural-question eval results (complements the phrase matcher in rag_natural_eval.py).

The phrase matcher requires every content word of a gold fact inside one clause, so a correct answer worded
differently ("tổng 185 tín chỉ, không tính GDTC" vs gold "Không tính ... GDTC, GDQP") counts as missing.
Here a model judge decides, fact by fact, whether the answer states the same thing as the gold fact. The gold
facts are machine-verified quotes from the sources; the judge never sees anything else and cannot add facts.
Forbidden facts and the stop/abstain logic stay deterministic.

  python evals/runners/rag_natural_judge.py --results <jsonl> --cases <jsonl> [--out <jsonl>] [--concurrency 3]

Writes <out> (default <results>.judged.jsonl) with per-row ``coverage`` and ``semantic_verdict``, then prints
the table. Judge calls are cached in <out>, so a rerun only judges new rows.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from concurrent import futures
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".claude/skills/ninerouter-workers/scripts"))
from common import load_config  # noqa: E402
from worker import call_router  # noqa: E402

_spec = importlib.util.spec_from_file_location("rag_natural_eval", Path(__file__).with_name("rag_natural_eval.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

ANSWERABLE = {"answer", "partial", "limit"}  # "limit": refusing is fine, answering must be right; "partial": answerable, but the best answer also states a limit (year/scope)
COVERAGE_OK = 0.75  # an answer is "helpful" when it states at least this share of the gold facts
PROMPT = """Bạn chấm câu trả lời của một chatbot học vụ. Cho: câu hỏi, câu trả lời, và danh sách "ý chuẩn" trích từ văn bản gốc.
Với MỖI ý chuẩn, quyết định câu trả lời có nêu cùng nội dung đó không. Diễn đạt khác vẫn tính là có nếu cùng ý và cùng số liệu, ngày, mã, mức tiền.
Tính là KHÔNG nếu thiếu ý đó, hoặc nêu số liệu/điều kiện khác.
Đặt "contradiction" = true chỉ khi câu trả lời khẳng định điều trái với một ý chuẩn.
%(extra)s
Chỉ trả về JSON: {"facts": [true, false, ...], "contradiction": false%(keys)s} với số phần tử "facts" bằng số ý chuẩn, đúng thứ tự.

Câu hỏi: %(question)s

Câu trả lời:
%(answer)s

Ý chuẩn:
%(facts)s
"""


def clean_answer(text: str) -> str:
    text = re.sub(r"\[CIT-\d+\]", "", text)
    return text.split("Gợi ý hỏi tiếp:")[0].strip()


def judge_row(cfg, model, case, row):
    facts = [" ".join(f.split()) for f in case.get("required_facts", [])]
    claims = case.get("forbidden_claims", [])
    conflict = case.get("conflict")
    if not facts:
        return {"facts": [], "contradiction": False, "claims": [False] * len(claims), "surfaced": None}
    extra, keys = "", ""
    if claims:
        extra += ("\nCác khẳng định SAI (không được coi là đáp án cho câu hỏi này). Với mỗi khẳng định, \"claims\"[i] = true nếu câu trả lời "
                  "khẳng định điều đó áp dụng cho trường hợp được hỏi; false nếu không nêu hoặc chỉ nêu như trường hợp/khóa/năm khác "
                  "được ghi rõ:\n" + "\n".join(f"{i + 1}. {c}" for i, c in enumerate(claims)) + "\n")
        keys += ', "claims": [false, ...]'
    if conflict:
        extra += ("\nCác nguồn có thể mâu thuẫn hoặc khác phiên bản. \"surfaced\" = true nếu câu trả lời nêu cả các giá trị: "
                  + " và ".join(map(str, conflict["values"])) + " (kể cả gắn với văn bản/năm khác nhau) hoặc nói rõ có sự khác nhau giữa các nguồn; "
                  "false nếu chỉ nêu một giá trị mà không nhắc sự khác nhau.\n")
        keys += ', "surfaced": false'
    prompt = PROMPT % {"question": case["question"], "answer": clean_answer(row["content"])[:3500],
                       "facts": "\n".join(f"{i + 1}. {f}" for i, f in enumerate(facts)), "extra": extra, "keys": keys}
    for _ in range(3):
        try:
            text, _info = call_router(cfg, model, [{"role": "user", "content": prompt}], 800, 120, 0.0)
            match = re.search(r"\{.*\}", text, re.S)
            data = json.loads(match.group(0))
            flags = [bool(x) for x in data["facts"]]
            claim_flags = [bool(x) for x in data.get("claims", [])] if claims else []
            if len(flags) == len(facts) and (not claims or len(claim_flags) == len(claims)):
                return {"facts": flags, "contradiction": bool(data.get("contradiction")), "claims": claim_flags,
                        "surfaced": bool(data.get("surfaced")) if conflict else None}
        except Exception:  # noqa: BLE001 -- retried, then reported as unjudged
            continue
    return None


def semantic_verdict(case, row, judged):
    kind = row["outcome"]
    if kind == "error":
        return "error"
    if case["expected"] not in ANSWERABLE:
        return "wrong" if kind in base.ANSWERED else "correct_stop"
    if case["expected"] == "limit":
        # Acceptable: honest refusal / clarification, or an answer that states the limit and asserts nothing false.
        if kind not in base.ANSWERED:
            return "correct_stop"
        if judged is None:
            return "unjudged"
        facts = judged["facts"]
        ok = not judged["contradiction"] and not any(judged.get("claims", [])) and (
            (sum(facts) / len(facts)) >= COVERAGE_OK if facts else True)
        return "correct_stop" if ok else "wrong"
    if any(base.scoring.fact_matches(f, row.get("content", "")) for f in case.get("forbidden_facts", [])):
        return "wrong"
    if kind in base.ANSWERED:
        if judged is None:
            return "unjudged"
        if judged["contradiction"] or any(judged.get("claims", [])):
            return "wrong"
        facts = judged["facts"]
        coverage = sum(facts) / len(facts) if facts else 1.0
        return "helpful" if coverage >= COVERAGE_OK else "incomplete"
    if kind == "clarify" and "chưa rõ nội dung" not in row.get("content", ""):
        return "guided"
    return "dead_end"


def reason_of(row) -> str:
    """Why an answerable question ended without an answer, read from the server's own wording."""
    text = row.get("content", "")
    if "chưa tìm thấy nguồn" in text:
        return "retrieval_miss"
    if "chưa xác minh được" in text:
        return "found_not_verified"
    if "cần được xác nhận trực tiếp" in text or "cần cán bộ hỗ trợ" in text or "quy tắc lưu lịch sử" in text:
        return "policy_guard"
    if "Bạn đang hỏi tiếp" in text or "chưa rõ nội dung" in text:
        return "clarify"
    return "other"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", required=True)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--out")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--show", help="comma list of semantic verdicts to print")
    args = parser.parse_args()

    cases = {}
    for line in Path(args.cases).read_text(encoding="utf-8").splitlines():
        if line.strip():
            c = json.loads(line)
            cases[c["case_id"]] = c
    rows = [json.loads(l) for l in Path(args.results).read_text(encoding="utf-8").splitlines() if l.strip()]
    out = Path(args.out or str(args.results) + ".judged.jsonl")
    cache = {}
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("judged") is not None or r.get("no_judge"):
                    cache[r["case_id"]] = r
    cfg = load_config()
    model = cfg.get("NINEROUTER_MODEL")

    def need(row):
        case = cases[row["case_id"]]
        return case["expected"] in ANSWERABLE and row["outcome"] in base.ANSWERED and row["case_id"] not in cache

    todo = [r for r in rows if need(r)]
    with futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for n, (row, judged) in enumerate(zip(todo, pool.map(lambda r: judge_row(cfg, model, cases[r["case_id"]], r), todo)), 1):
            cache[row["case_id"]] = {"case_id": row["case_id"], "judged": judged}
            print(f"judge {n}/{len(todo)} {row['case_id']}", flush=True)

    by_style, reasons = defaultdict(Counter), Counter()
    result_rows = []
    for row in rows:
        case = cases[row["case_id"]]
        judged = (cache.get(row["case_id"]) or {}).get("judged")
        verdict = semantic_verdict(case, row, judged)
        row.update(semantic_verdict=verdict, judged=judged,
                   coverage=(sum(judged["facts"]) / len(judged["facts"])) if judged and judged["facts"] else None)
        by_style[row.get("style") or "?"][verdict] += 1
        by_style["ALL"][verdict] += 1
        if case["expected"] in ANSWERABLE and verdict in {"dead_end", "guided"}:
            reasons[reason_of(row)] += 1
        result_rows.append(row)
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in result_rows) + "\n", encoding="utf-8")

    for style, counter in sorted(by_style.items()):
        total = sum(counter.values())
        print(f"{style:10} n={total:3} " + " ".join(f"{k}={counter[k]}({counter[k] / total:.0%})" for k in
              ("helpful", "incomplete", "guided", "dead_end", "wrong", "correct_stop", "unjudged", "error") if counter[k]))
    answerable = [r for r in result_rows if cases[r["case_id"]]["expected"] in ANSWERABLE]
    conflicts = [r for r in result_rows if cases[r["case_id"]].get("conflict") and r.get("judged")]
    if conflicts:
        surfaced = sum(bool(r["judged"].get("surfaced")) for r in conflicts)
        print(f"conflict cases judged={len(conflicts)} surfaced_both_or_flagged={surfaced / len(conflicts):.0%}")
    if answerable:
        good = sum(r["semantic_verdict"] == "helpful" for r in answerable)
        useful = sum(r["semantic_verdict"] in {"helpful", "guided"} for r in answerable)
        print(f"answerable n={len(answerable)} helpful={good / len(answerable):.0%} helpful_or_guided={useful / len(answerable):.0%}")
    print("why answerable questions got no answer:", dict(reasons))
    if args.show:
        for r in result_rows:
            if r["semantic_verdict"] in args.show.split(","):
                print(f"\n[{r['semantic_verdict']}] {r['case_id']} {r['style']} cov={r['coverage']} :: {r['question'][:150]}\n   -> {r['outcome']} :: {r['content'][:260].replace(chr(10), ' | ')}")


if __name__ == "__main__":
    main()
