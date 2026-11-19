# Held-out set 2 (written 2026-11-19, before any run)

Three synthetic documents of structures the first held-out set lacks, 6 questions each, gold checked by code:

| Document | Structure | Kinds |
|---|---|---|
| `quy-che-thuc-tap.txt` | numbered articles that refer to each other ("theo quy định tại Điều 6") | cross reference, general rule, deadline |
| `hoc-bong-hai-tang.txt` | table with a two-level reading (group of programmes x scholarship level) | table cell, absent row (abstain) |
| `dang-ky-hoc-phan.txt` | dated notice with exceptions and cohort-specific rows | scoped row, exception, absent cohort (abstain) |

Rules for using it (same as `unseen-docs-heldout`): run it ONCE, record the score, and do not tune the code against individual questions. A failure is written down and addressed with a general mechanism, then this set joins the regression sets.

    PYTHONPATH="data/rag_v2_vendor;services/api/src;services/worker/src;scripts;." infra/local/rag-fixture/.venv/Scripts/python.exe -B -X utf8 \
      evals/runners/rag_unseen_doc_eval.py --docs evals/datasets/unseen-docs-heldout-2 --out evals/results/unseen-docs/heldout2-first-run.json

Needs the embedding server (18081) and the gateway sidecar (8025); about 60 provider calls. `--no-llm-check` validates only the gold (done: 18 questions over 3 documents verified).
