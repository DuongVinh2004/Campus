"""Full Windows regression with the environment each test group is written for.

  .venv/Scripts/python.exe -B evals/runners/run_full_regression.py [--out DIR]

Some groups only run inside a registered fixture directory (their helper scripts refuse any other temp directory) or need an
evidence directory, so one plain `pytest tests` leaves them failing for environmental reasons. This runner starts pytest once
for the main suite and once for each such group with its registered base temp directory, then merges the failures into
`failures.txt`. It creates new folders only (under infra/local/...); nothing existing is touched.

Four tests stop on purpose because a human approval is missing and are NOT worked around here: two migration-source guards
(tests/integration/rag_fixture/test_guard.py, test_retrieval_scope_migration.py) and two dependency approvals
(tests/unit/dependency_resolution/test_verifier.py). They fail until someone reviews the new migrations / candidate set.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "infra/local"
STAMP = time.strftime("%Y%m%d%H%M%S")
PY = [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfE"]

# (name, test paths, base temp directory relative to infra/local, extra pytest args)
GROUPS = [
    ("stream-c", ["tests/unified_final", "tests/integration/test_unified_storage_completion.py"],
     "unified-ai-parallel-20261015-01/stream-c/checks/reg-" + STAMP, []),
    ("staff-12", ["tests/integration/test_unified_staff12.py"], "unified-ai-20261015-12/reg-" + STAMP, []),
    ("stream-a", ["tests/unified_workflow13a"], "unified-ai-parallel-20261015-01/stream-a/reg-" + STAMP, []),
    ("stream-b", ["tests/unified_personal13b"], "unified-ai-parallel-20261015-01/stream-b/reg-" + STAMP, []),
]


def free_backend() -> str:
    checks = LOCAL / "unified-ai-completion-20261015-01/checks"
    for number in range(100):
        if not (checks / f"backend-{number:02d}").exists():
            (checks / f"backend-{number:02d}").mkdir()
            return f"unified-ai-completion-20261015-01/checks/backend-{number:02d}/basetemp"
    raise SystemExit("no free completion backend id (00-99)")


def run(args: list[str], env: dict, log: Path) -> tuple[int, str]:
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    text = result.stdout + result.stderr
    log.write_text(text, encoding="utf-8")
    return result.returncode, text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / f"evals/results/final-regression-{STAMP}"))
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    evidence = LOCAL / "learning-test-evidence-20261116"
    evidence.mkdir(exist_ok=True)
    env = dict(os.environ, LEARNING_TEST_ROOT=str(evidence), PYTHONPATH=os.pathsep.join(
        [str(ROOT / "services/worker/src"), str(ROOT / "scripts"), os.environ.get("PYTHONPATH", "")]))
    grouped = [path for _, paths, _, _ in GROUPS for path in paths] + ["tests/unified_completion"]
    runs = [("main", [*PY, f"--basetemp={ROOT / f'.pytest-tmp-reg-{STAMP}'}", "tests", *[f"--ignore={p}" for p in grouped]])]
    for name, paths, base, extra in GROUPS:
        (LOCAL / base).parent.mkdir(parents=True, exist_ok=True)
        runs.append((name, [*PY, f"--basetemp={LOCAL / base}", *extra, *paths]))
    runs.append(("completion", [*PY, "-p", "unified_completion_pytest", f"--basetemp={LOCAL / free_backend()}", "tests/unified_completion"]))
    failures, summary = [], []
    for name, command in runs:
        started = time.time()
        code, text = run(command, env, out / f"pytest-{name}.log")
        final = [line for line in text.splitlines() if re.search(r"\d+ (passed|failed|error)", line)][-1:]
        summary.append(f"{name}: exit {code}, {final[0].strip() if final else 'no summary'} ({time.time() - started:.0f} s)")
        failures += sorted({re.sub(r" - .*", "", line) for line in text.splitlines() if line.startswith(("FAILED ", "ERROR "))})
    (out / "failures.txt").write_text("\n".join(sorted(set(failures))) + "\n", encoding="utf-8")
    (out / "summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    print(f"{len(set(failures))} failing items -> {out / 'failures.txt'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
