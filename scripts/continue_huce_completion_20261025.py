"""Append-only evidence preparation for the second HUCE completion run."""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "infra/local/huce-completion-20261025-02"
OLD = ROOT / "infra/local/huce-evidence-20261025-01"
CORPUS = ROOT / "infra/local/huce-corpus-completion-20261024-01"
REGULATION = "253eb450-c57a-79a7-84a4-b0d85e12de1c"


def checked(path):
    path = path.resolve(strict=False)
    if path == ROOT.resolve() or not path.is_relative_to(ROOT.resolve()):
        raise ValueError("Exact workspace child required")
    return path


def read(path):
    return json.loads(checked(path).read_text(encoding="utf-8"))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path = checked(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str)


def preflight():
    status = subprocess.run(["git", "status", "--short"], cwd=ROOT,
        capture_output=True, encoding="utf-8", check=True)
    files = [OLD / n for n in ("completion-receipt-01.json", "final-verdict-02.json",
        "source-status-final-01.json", "remaining-evidence-worklist-01.json",
        "source-dispositions-final-01.json")]
    files += [CORPUS / n for n in ("candidate-plan-08.json", "candidate-release-08.json",
        "candidate-integrity-05.json")]
    values = {str(f.relative_to(ROOT)): read(f) for f in files}
    sources = values[str((OLD / "source-status-final-01.json").relative_to(ROOT))]["sources"]
    counts = {}
    for row in sources:
        counts[row["category"]] = counts.get(row["category"], 0) + 1
    save(OUT / "preflight-01.json", {"at": datetime.now(UTC), "workspace": str(ROOT.resolve()),
        "status": status.stdout, "warnings": status.stderr,
        "handoff_sha256": {str(f.relative_to(ROOT)): sha(f.read_bytes()) for f in files},
        "source_counts": counts, "baseline_release": values[str((CORPUS / "candidate-release-08.json").relative_to(ROOT))],
        "scope": "Additive local engineering and public source inspection; retain all prior data and controls"})
    print(json.dumps({"source_counts": counts, "handoff_files_read": len(values), "out": str(OUT)}))


def text_pages(start, end):
    record = read(ROOT / "data/huce-public-20261013/regulations-human-reviewed.json")
    for chunk in record["chunks"]:
        if start <= chunk["page"] <= end:
            print(f"PDF PAGE {chunk['page']}\n{chunk['text']}\n")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["preflight", "regulation-text"])
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=26)
    args = parser.parse_args()
    if args.command == "preflight":
        preflight()
    else:
        text_pages(args.start, args.end)
