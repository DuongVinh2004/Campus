"""Do two machines produce the same query vectors? (rollout step 1.11: Windows vs Linux ONNX Runtime)

  python scripts/embedding_parity.py dump --out vectors-<os>.json [--count 200]
  python scripts/embedding_parity.py compare --a vectors-windows.json --b vectors-linux.json [--min-cosine 0.9999]

`dump` embeds the same sample of real-style questions with the production model, tokenizer and engine class of this
operating system (m1_platform_20261115.CPU) and writes plain JSON. `compare` reports the lowest cosine similarity and the
largest absolute difference between the two files and exits 1 when any vector is below the threshold.
Only questions from the evaluation datasets are embedded; no student data, no network, no paid call.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "infra/local/rag-fixture")]
QUESTION_FILES = ("real-style-20261114.jsonl", "natural-cases-20261114.jsonl")


def sample_questions(count: int) -> list[str]:
    seen, questions = set(), []
    for name in QUESTION_FILES:
        for line in (ROOT / "evals/datasets/rag-v2" / name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                question = json.loads(line)["question"]
                if question not in seen:
                    seen.add(question)
                    questions.append(question)
    return questions[:count]


def dump(out: Path, count: int) -> None:
    import platform
    import time

    from m1_platform_20261115 import CPU
    from m2_inference_20261012_74 import Session
    from onnx_graph_20261011_30 import DEST
    from token_envelope_20261007_25 import TokenEnvelope

    envelope, engine = TokenEnvelope(), CPU()
    session = Session(engine, DEST / "model.onnx")
    vectors, started = {}, time.perf_counter()
    try:
        for question in sample_questions(count):
            ids = envelope.models["embedding"].encode(question, add_special_tokens=True).ids
            result, _ = session.run([ids], b"sentence_embedding")
            vectors[question] = [float(v) for v in result[0]]
    finally:
        session.close()
        engine.close()
    out.write_text(json.dumps({"platform": platform.platform(), "python": sys.version.split()[0], "count": len(vectors),
                               "seconds": round(time.perf_counter() - started, 1), "vectors": vectors}), encoding="utf-8")
    print(json.dumps({"written": str(out), "count": len(vectors), "seconds": round(time.perf_counter() - started, 1)}))


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def compare(a_path: Path, b_path: Path, minimum: float) -> int:
    a, b = json.loads(a_path.read_text(encoding="utf-8")), json.loads(b_path.read_text(encoding="utf-8"))
    shared = sorted(set(a["vectors"]) & set(b["vectors"]))
    if not shared:
        raise SystemExit("no common questions")
    cosines = [cosine(a["vectors"][q], b["vectors"][q]) for q in shared]
    worst_abs = max(abs(x - y) for q in shared for x, y in zip(a["vectors"][q], b["vectors"][q]))
    report = {"compared": len(shared), "min_cosine": min(cosines), "mean_cosine": sum(cosines) / len(cosines),
              "max_abs_difference": worst_abs, "threshold": minimum, "a": a["platform"], "b": b["platform"],
              "passed": min(cosines) >= minimum}
    print(json.dumps(report, indent=1))
    return 0 if report["passed"] else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("dump", "compare"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--a", type=Path)
    parser.add_argument("--b", type=Path)
    parser.add_argument("--min-cosine", type=float, default=0.9999)
    args = parser.parse_args()
    if args.command == "dump":
        if not args.out:
            parser.error("--out required")
        dump(args.out, args.count)
    else:
        raise SystemExit(compare(args.a, args.b, args.min_cosine))


if __name__ == "__main__":
    main()
