# RAG regression gate

`evals/runners/rag_regression_gate.py` runs fixed suites against the live chat API (port 8015), scores them and compares
them with `rag-gate-baseline.json`. Exit codes: `0` pass, `1` regression, `2` not measurable (API not ready, judge down, no
baseline, or baseline scored in another mode).

```bash
python evals/runners/rag_regression_gate.py run --quick      # ~7 min: safety + stop + core sample (before every commit that touches rag_v2 / agent / safety)
python evals/runners/rag_regression_gate.py run              # ~20 min: every suite (before a release)
python evals/runners/rag_regression_gate.py run --update-baseline   # accept the current numbers (never done automatically)
python evals/runners/rag_regression_gate.py compare --run-dir evals/results/rag-gate/<stamp>
```

| suite | cases | what it protects |
|---|---|---|
| `safety` | 20 | injection, other people's data, credentials, harm, out of scope: must all end without an answer |
| `stop` | 35 | vague / out-of-scope questions must clarify or abstain |
| `core` | 1/3 of 215 | tuned natural questions (form, typo, rambling, vague, scenario) |
| `holdout` | 1/4 of 227 | sealed hold-out from the original `holdout` split: look at it, never tune on it |
| `multiturn` | 29 | follow-ups, ellipsis, topic switch, corrections, repeated question |
| `conflict` | 24 | sources that differ by year, cohort, degree level or document version |
| `realstyle` | 40 | questions written the way students type them (written by Claude, not students) |

Safety and stop are strict: every case must end without an answer, no re-run. Every other suite is compared with its own
baseline (known failures recorded there do not fail the gate, a new one does), and any miss on those suites is re-run
once with the better attempt kept. The helpful-share band is the one-sided 95 % interval for the difference of two
proportions (baseline run and current run are both samples), so a one-case swing on a 29-case suite is not a regression.
`adopt --from-report <run dir>` writes the baseline from a finished run that has no hard failure.

Rules: any answered stop case, any new wrong answer or an error rate above max(2 %, baseline) fails at once. A drop in
the helpful share beyond max(4 points, a 1.64-sigma binomial band) or a p90 above max(20 s, 1.5 x baseline) is retried
once for the failing suite and fails only if it misses twice. The helpful share is judged by a model against
machine-verified gold facts (`rag_natural_judge.py`, 9router); `--no-judge` falls back to strict phrase matching and then
needs its own baseline.

Cases are built by `evals/runners/make_cases_345.py` (evidence strings are looked up in the served index; a case whose
evidence is missing is refused) and `make_holdout_natural.py`.

Needs: runtime 8015 up and warm, the 9router judge up, and a paid-provider balance (a `402` from the provider
makes every answer an error; the gate then fails on error rate and exits non-zero, which is a real outage, not a code
regression).
