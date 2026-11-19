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

## First run (2026-11-20, once, nothing tuned): 16/18 (89%)

`evals/results/unseen-docs/heldout2-first-run.json`. By kind: table cell 3/3, deadline 3/3, exception 2/2, scoped row 1/1, cross reference 1/1, abstain 2/2, prose 4/5, general rule applies 0/1.

- **tt-04 (marked wrong) is a flaw in my gold, not in the system.** The answer "điểm của người hướng dẫn (40%) và điểm báo cáo (60%)" is correct; I had listed "40%" as forbidden although the document states both weights. Raw score stays 16/18; with that case regraded it would be 17/18.
- **tt-06 (dead end) is a real weakness.** "Sinh viên ngành Cầu đường thực tập tối thiểu bao nhiêu tuần?": the document gives a general rule (8 weeks) and names only one exception (Kiến trúc, 10 weeks). The question names a programme that the document does not mention; the system found the source but refused ("chưa xác minh được phát biểu"), instead of answering with the general rule and saying the programme is not named. The earlier scope-name mechanism handles tables; this is the same class in running prose. To be handled with a general mechanism (not a rule for this sentence), then this set joins the regression sets.
