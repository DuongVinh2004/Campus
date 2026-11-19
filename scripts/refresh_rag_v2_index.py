"""Build a candidate RAG v2 index for the release now serving, so newly published documents become searchable.

Why: the v2 index is a snapshot bound to one release generation. After a publication the runtime keeps answering
from the old snapshot and /health/ready reports `stale` until a new snapshot is built and the API is restarted
on it. This script only builds the candidate in fresh directories (existing indexes are never touched); it does
not change the splitter, the embedding model, the batch size of the original build or any retrieval setting,
and it does not activate anything. Existing vectors are reused from --base, so only new units are embedded.

Activation is a separate, deliberate step: stop the API (parent and workers) and start it with
`--rag-v2-index <candidate>` (see the last lines printed).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> subprocess.CompletedProcess:
    environment = {**os.environ, "PYTHONPATH": os.pathsep.join(["data/rag_v2_vendor", "services/api/src", "."])}
    return subprocess.run([sys.executable, "-B", "-X", "utf8", *command], cwd=ROOT, env=environment,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", type=Path, default=Path("data/rag_v2_index/embedded2"),
                        help="Validated index currently serving; its vectors are reused")
    parser.add_argument("--batch-size", type=int, default=1, choices=range(1, 21),
                        help="Embedding batch size; 1 matches the build of the serving index")
    parser.add_argument("--tag", help="Name suffix of the new directories (default: timestamp); must be unused")
    parser.add_argument("--json", action="store_true", help="Print one compact JSON line only (for the ingestion worker)")
    args = parser.parse_args(argv)
    if args.tag is not None and not re.fullmatch(r"[A-Za-z0-9-]{4,40}", args.tag):
        parser.error("--tag: 4-40 characters A-Z a-z 0-9 -")
    stamp = args.tag or datetime.now().strftime("%Y%m%d-%H%M%S")
    corpus = Path("evals") / f"corpus-refresh-{stamp}"
    output = Path("data/rag_v2_index") / f"embedded-{stamp}"
    base = args.base if args.base.is_absolute() else ROOT / args.base
    if not (base / "manifest.json").is_file():
        print(f"REFRESH_FAILED: base index missing: {args.base}", file=sys.stderr)
        return 1

    exported = run(["evals/runners/corpus_export.py", "--output-dir", str(corpus)])
    if not args.json:
        print(exported.stdout.strip().splitlines()[-1] if exported.stdout.strip() else exported.stderr[-300:])
    if not (ROOT / corpus / "served-chunks.jsonl").is_file():
        print("REFRESH_FAILED: corpus export did not produce a corpus", file=sys.stderr)
        return 1

    built = run(["scripts/rag_v2_build_index.py", "--corpus", str(corpus / "served-chunks.jsonl"), "--output", str(output),
                 "--embed", "--base", str(args.base), "--batch-size", str(args.batch_size)])
    if built.returncode:
        print("REFRESH_FAILED:", (built.stderr or built.stdout)[-400:], file=sys.stderr)
        return built.returncode

    old = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    new = json.loads((ROOT / output / "manifest.json").read_text(encoding="utf-8"))
    summary = {key: new.get(key) for key in ("release_id", "generation", "policy_generation", "chunk_count", "unit_count",
                                              "embedding_status", "embedding_revision")}
    summary["added_units"] = (new.get("unit_count") or 0) - (old.get("unit_count") or 0)
    summary["same_release_as_base"] = (old.get("release_id"), old.get("generation")) == (new.get("release_id"), new.get("generation"))
    result = {"candidate_index": output.as_posix(), "corpus": corpus.as_posix(), **summary}
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\nNot activated. To serve it: stop the API parent and its workers, then start the launcher with\n"
          f"  knowledge_platform_runtime.py start --engine v2 --rag-v2-index {output} --frontend-name <live snapshot>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
