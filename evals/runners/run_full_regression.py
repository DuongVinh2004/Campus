"""Full Windows regression with the environment each test group is written for.

  .venv/Scripts/python.exe -B evals/runners/run_full_regression.py [--out DIR]
  python -B evals/runners/run_full_regression.py --ci [--out DIR]     # portable subset for a clean Linux checkout (CI)

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

# --ci runs one pytest over the tests that need nothing outside the repository: no registered fixture directories under
# infra/local, no model server, no database server, no paid provider. Every other tests/ directory is listed as not run,
# so a green CI run is never read as "everything passed".
CI_PATHS = [
    "tests/unit", "tests/integration/retention", "tests/evals/test_audit_remediation_gate.py", "tests/delivery", "tests/campus_ops",
    # Operations, alerts, backup, sign-in and nightly-check tests: they use temporary files, fake HTTP and fake clocks only.
    "tests/operations/test_backup_status.py", "tests/operations/test_rehearse_restore.py", "tests/operations/test_rehearsal_units.py",
    "tests/operations/test_offsite.py", "tests/operations/test_watchdog.py", "tests/evals/test_nightly_retrieval.py",
    "tests/api/test_admin_ops.py", "tests/api/test_knowledge_freshness.py", "tests/api/test_oidc_login.py", "tests/api/test_ops_metrics_hooks.py",
    "tests/api/test_gateway_sidecar.py", "tests/api/test_chat_admission.py", "tests/api/test_abuse_limits.py", "tests/api/test_answer_quality.py",
    # Answer gaps, the retrieval check after a release, the backup tool's unreadable-file rule and the test-folder lister.
    "tests/api/test_answer_gaps.py", "tests/api/test_gap_reports.py", "tests/api/test_release_check.py", "tests/operations/test_backup_skip.py", "tests/maintenance",
]

# Inside the paths above, these import helper modules that exist only under infra/local/rag-fixture (not in the repository), so a
# clean checkout cannot even collect them. They stay in the local full run and are listed as not run in --ci.
CI_IGNORE = [
    "tests/unit/runtime_review", "tests/unit/conversation/test_m2_info_snapshot.py",
    # These read retained real documents or measurement helpers under data/, .tooling/ or infra/local, none of which is tracked.
    "tests/unit/agent/test_multi_agent_admission.py", "tests/unit/agent/test_public_discipline_rules.py",
    "tests/unit/assistance/test_baseline_evidence.py", "tests/unit/conversation/test_m2_reference_resolution_73.py",
    "tests/unit/learning/test_pdf_subprocess.py", "tests/unit/retrieval/test_advanced_policy_regeneration.py",
    "tests/unit/retrieval/test_advanced_rag.py", "tests/unit/retrieval/test_conjunctive_conditions.py",
    "tests/unit/retrieval/test_huce_calendar_source_rows.py", "tests/unit/retrieval/test_huce_common_core_slices.py",
    "tests/unit/retrieval/test_huce_common_support_sources.py", "tests/unit/retrieval/test_huce_conference_sources.py",
    "tests/unit/retrieval/test_huce_discovery.py", "tests/unit/retrieval/test_huce_english_primary_sources.py",
    "tests/unit/retrieval/test_huce_fee_units.py", "tests/unit/retrieval/test_huce_ict_rules_sources.py",
    "tests/unit/retrieval/test_huce_instruction_quantities.py", "tests/unit/retrieval/test_huce_irregular_course_line.py",
    "tests/unit/retrieval/test_huce_it_related_programmes.py", "tests/unit/retrieval/test_huce_native_table_variants.py",
    "tests/unit/retrieval/test_huce_raster_curriculum.py", "tests/unit/retrieval/test_huce_service_release.py",
    "tests/unit/retrieval/test_public_faq_index.py", "tests/unit/retrieval/test_public_rag_gateway_concurrency.py",
    "tests/unit/retrieval/test_public_rag_wiring.py", "tests/unit/retrieval/test_public_source_excerpts.py",
    "tests/unit/retrieval/test_tuition_credit_questions.py",
]

# (name, test paths, base temp directory relative to infra/local, extra pytest args)
GROUPS = [
    ("stream-c", ["tests/unified_final", "tests/integration/test_unified_storage_completion.py"],
     "unified-ai-parallel-20261015-01/stream-c/checks/reg-" + STAMP, []),
    ("staff-12", ["tests/integration/test_unified_staff12.py"], "unified-ai-20261015-12/reg-" + STAMP, []),
    ("stream-a", ["tests/unified_workflow13a"], "unified-ai-parallel-20261015-01/stream-a/reg-" + STAMP, []),
    ("stream-b", ["tests/unified_personal13b"], "unified-ai-parallel-20261015-01/stream-b/reg-" + STAMP, []),
]


def ci_not_run(paths: list[str] | None = None) -> list[str]:
    """Test directories and files the CI subset does not cover. A directory that is only partly covered is opened up."""
    covered = list(CI_PATHS if paths is None else paths)

    def walk(directory: Path) -> list[str]:
        missing = []
        for entry in sorted(directory.iterdir()):
            rel = entry.relative_to(ROOT).as_posix()
            if entry.name.startswith((".", "__")) or not (entry.is_dir() or entry.name.startswith("test_")):
                continue
            if rel in covered:
                continue
            if entry.is_dir() and any(path.startswith(rel + "/") for path in covered):
                missing += walk(entry)
            else:
                missing.append(rel)
        return missing

    return sorted(walk(ROOT / "tests") + ([] if paths is not None else CI_IGNORE))


def run_ci(out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    evidence = out / "learning-evidence"  # LEARNING_TEST_ROOT must exist and is never reused between runs
    evidence.mkdir(exist_ok=True)
    env = dict(os.environ, LEARNING_TEST_ROOT=str(evidence), PYTHONPATH=os.pathsep.join(
        [str(ROOT / "services/worker/src"), str(ROOT / "scripts"), os.environ.get("PYTHONPATH", "")]))
    command = [*PY, f"--basetemp={out / 'basetemp'}", *CI_PATHS, *[f"--ignore={p}" for p in CI_IGNORE]]
    started = time.time()
    code, text = run(command, env, out / "pytest-ci.log")
    final = [line for line in text.splitlines() if re.search(r"\d+ (passed|failed|error)", line)][-1:]
    failures = sorted({re.sub(r" - .*", "", line) for line in text.splitlines() if line.startswith(("FAILED ", "ERROR "))})
    not_run = ci_not_run()
    summary = [f"ci: exit {code}, {final[0].strip() if final else 'no summary'} ({time.time() - started:.0f} s)",
               "ran: " + ", ".join(CI_PATHS),
               f"NOT RUN in --ci ({len(not_run)}): " + ", ".join(not_run)]
    (out / "failures.txt").write_text("\n".join(failures) + ("\n" if failures else ""), encoding="utf-8")
    (out / "summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    print(f"{len(failures)} failing items -> {out / 'failures.txt'}")
    return 1 if code != 0 or failures else 0


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
    parser.add_argument("--ci", action="store_true", help="portable subset for a clean Linux checkout")
    args = parser.parse_args()
    if args.ci and args.out == str(ROOT / f"evals/results/final-regression-{STAMP}"):
        args.out = str(ROOT / f".ci-evidence/regression-{STAMP}")
    out = Path(args.out)
    if args.ci:
        return run_ci(out)
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
