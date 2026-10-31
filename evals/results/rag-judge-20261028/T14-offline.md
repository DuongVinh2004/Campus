# T14 — thin answers: offline diagnosis and scoped fix

## Scope and evidence

Read REPORT-v2 §13–§15 first. Used only the saved dev gate cases,
`runs/ab-neg.json`, the served corpus, stored index units and
`data/rag_v2_debug/generation.jsonl`. No provider/embedding/rerank calls, runtime,
end-to-end runner, holdout inspection, dataset changes or scoring changes.

Evidence: model-written dev cases with source spans checked by code; stored
generator statements replayed through deterministic checks; synthetic unit tests.
Real-user usability and the changed end-to-end answers remain unmeasured.

Snapshot SHA-256:

- `runs/ab-neg.json`: `c55746b7948019ba2cdbb2481f81a96727392646cd139a322c45ec52dc7cb8ab`
- `data/rag_v2_debug/generation.jsonl`: `0480f5a5088255c167460144b402ca1a3d6fc85b6daf5e853231c9d6df564a0b`

`fact_matches` identifies **10 thin answers among 116 answerable cases**. All
10 remain thin under the unchanged scorer on the saved answers: this patch does
not rewrite results or claim a new A1 measurement.

Two evidence limitations matter:

1. `thin_diag.py` imports an embed function that POSTs to `127.0.0.1:18081/embed`.
   It was inspected, not executed unchanged. Its context coverage calculation was
   reproduced against the *captured parent IDs*, without retrieving new vectors.
2. All matching generator captures still contain the reverted `asked` field,
   and captures have no run ID. They describe the preceding experiment, not a
   proven exact draft from `ab-neg`. The captured decision for Q2-0063 is even
   `no_source`, whereas its ab-neg result is `answer`. Replayed rejection reasons
   must not be presented as exact ab-neg semantic verdicts. The failed negation
   experiment also used different checks from the current restored code.

The old diagnostic's `fact_matches(fact, entire_context)` can give false coverage:
unrelated occurrences of words across a page satisfy the 75% word rule. For
example, the registration conditions and an unrelated academic-warning clause
collectively match the dual-degree stopping facts without stating that rule.
The analysis below therefore also checks each **whole gold quote inside one
source row**, and reads the surrounding source text. A missing gold quote alone
is not proof that no paraphrase exists; in these cases the surrounding text
confirms that the relevant rule/procedure is missing.

## Each thin case

IDs below are the exact case IDs in `cases-dev-gate.jsonl`.

| Case | Missing fact and observed answer | Cause supported by the saved evidence |
|---|---|---|
| R2-A2-0015 | Needs `361883 – 10` (Đồ án tốt nghiệp); final instead gives the programme total `190TC`. | **Generator omission / wrong answer focus.** The final cited row `…ca53-7503-b856-0942b8f662cf` contains `361883 – 10` immediately before “Đồ án tốt nghiệp”. Outcome `answer` means compose did not discard a statement from that final draft. There is no matching generator capture, so its exact draft is unavailable. |
| R2-Q1-0069 | Final gives the earliest registration year and entry requirements; omits stopping CT2 when CT1 is below average or under an academic warning, in the following semester. Scorer flags only `cảnh báo kết quả học tập`. | **Missing relevant context / source selection**, corroborated by the captured context. The registration gold row `…0e09…` is present, stopping-rule row `…0e0c…` absent. Captured generator also writes only registration conditions, with no deterministic rejection. The warning terms in another clause cause false coverage in thin_diag. Lexical-only replay places the missing row at rank 2, but diversity evicts it. Exact live retrieval versus packing cannot be separated without candidate IDs from that run. |
| R2-Q1-0070 | Same missing stopping rule in the unaccented variant; scorer again flags only the warning fact. | **Missing relevant context / source selection**, same mechanism as 0069. Captured gold coverage is registration=true, stopping=false; captured statements pass deterministic checks and cover registration only. Lexical-only missing-row rank is 3. |
| R2-Q1-0071 | “1486 song bằng đăng ký/dừng”: final gives generic registration and the administrative application process, omitting earliest year and stopping conditions. | **Retrieval relevance / context selection.** Neither gold rule is in captured context: top source is generic Điều 7, plus handbook administrative steps and unrelated documents. Captured statements also answer those topics. Lexical-only registration row is rank 8, stopping row rank 19; direct top-12 repairs only the first part. No evidence that relaxing a verifier would repair this case. |
| R2-Q1-0072 | Final correctly states stopping conditions but omits earliest registration in year two. | **Missing relevant context / source selection.** Capture contains stopping row `…0e0c…`, but no registration rule. “Trình độ năm thứ hai” occurs in unrelated classification text; it does not establish permission to start CT2. Captured single stopping statement passes deterministic replay. Lexical-only registration row at rank 3 is evicted by the old diverse shortlist. |
| R2-Q1-0091 | Needs the prohibition on sharing accounts/passwords **under any form**; final partial describes the IT centre's incident-response duties. | **Generator omission** of the sharing prohibition despite exact gold in U4/U5. Neither captured draft writes that prohibition. **Additional deterministic false rejection:** the captured correct “báo ngay với cấp trên và Trung tâm CNTT & CSDL” statement gets `NEGATION_MISMATCH` from unrelated negated phrases. Restoring that reporting statement alone would not fill the two missing sharing facts. Other captured deterministic-pass statements absent from final are consistent with semantic filtering, but exact ab-neg semantic verdicts are not saved. |
| R2-Q2-0025 | Final partial keeps parent/GVCN signatures, omitting minimum one semester and the disciplinary exclusion. | **Verifier loss is implicated; exact ab-neg stage is not recoverable.** Context contains both rules and signatures. Captured minimum-semester statement passes deterministic replay but omits the disciplinary condition; rejecting that incomplete permission semantically is reasonable. Captured exclusion paraphrase “không áp dụng cho…” gets deterministic `NEGATION_MISMATCH` because the source says “không thuộc…”. This is a real paraphrase false rejection in replay, not justification to disable polarity checks. Captured and final signature lists differ, so the exact ab-neg rejected wording cannot be asserted. |
| R2-Q2-0028 | Same two missing conditions; final partial keeps duration accounting and signatures. | **Verifier loss, semantic rejection is the leading hypothesis.** Captured combined statement includes both minimum semester and exclusion, is supported by Điều 14.1(d), and passes deterministic checks; a separate disciplinary-exclusion statement passes too. Both are absent from ab-neg final. Without matching run-tagged draft/semantic output this cannot be proven an exact semantic false rejection. The final's duration statement was not in the captured draft. |
| R2-Q2-0063 | “trạm y tế thông tin khám”: final gives only the handbook's table-of-contents entry; missing patient identity fields and reason for examination. | **Retrieval relevance / missing procedure context.** Capture contains the contents page `…5cfa…`, not procedure row `…5fd0…`. Captured model returns `no_source`, confirming this is not an exact ab-neg draft. Word-bag context matching is spurious: words occur in unrelated rows. Lexical-only procedure row is rank 4 but the old diverse shortlist drops it. |
| R2-Q2-0086 | Final partial says **at least 8** characters and character types, omitting password reuse guidance; gold handbook says **longer than 8** and no reuse. | **Retrieval/context selection chooses a different policy**, with a secondary captured deterministic rejection of a sharing statement. Handbook row `…617b…` is absent from capture; cited decision row `…e65a…` really says at least 8. `>=8` and `>8` are not scoring equivalents. Captured sharing text is not the requested reuse rule. No scorer relaxation is justified. |

Thus the largest common group is **six cases with the needed rule/procedure
absent from the captured context**, rather than six demonstrated omissions of
facts actually available to the generator. Two further cases have generator
omission evidence and two implicate verifier loss. None of these ten is solely
a true-paraphrase scoring artefact. The scorer also *understates* omissions in
0069/0070/0071/0091 by matching unrelated words in the final answer.

## Chosen fix

`retrieval/hybrid.py` previously always built a diverse shortlist of
`max(10, preselect)` units. The service requests `final_limit=12` with reranking
disabled, but the shortlist both limited the result to 10 and gave lower-ranked
documents slots before relevant sibling clauses. Sorting that shortlist back
into RRF order could not restore discarded clauses.

When `rerank_deadline_s == 0`, take the fused top `final_limit` directly. Diversity
remains the shortlist for an enabled reranker. This changes four lines in the
retriever (comment plus selection), with no document/question rules and no new
model calls. The existing scope/authorization filtering, RRF formula, parent-row
packing order, six-row/19,000-byte context budget, generation schema, polarity,
value and semantic checks are preserved.

The other candidates were not selected:

- More context bytes/rows add cost and cannot recover a clause already removed
  by preselection. The shortlist defect has a smaller fix.
- No true scoring equivalence accounts for the missing rules. In particular
  “at least” cannot be equated with “longer than”.
- Negation deferral and `asked` already failed end-to-end (§15); neither is
  repeated. Local verifier paraphrase issues remain documented above.

## Reproducible offline comparison

Run `runs/t14_offline.py` with `.venv/Scripts/python.exe -B`. It prints JSON,
writes no files, imports the unchanged `fact_matches`, replays captures, and
compares the old diverse shortlist against the patched retriever using **BM25
only**, an explicitly empty vector branch, actual `AuthorizedIndex` parent
construction, the current scope/early gates and service packing budgets. This
isolates selection; it is not a reconstruction of live hybrid rankings.

| Evidence | Before | After |
|---|---:|---:|
| All gold quotes present in packed context, /116 answerable cases | 93 | 98 |
| Cases skipped before retrieval, in both versions | 1 | 1 |
| Thin cases gaining complete gold context | — | 4 |
| Cases losing complete gold context in this lexical-only comparison | — | 0 |

Gains: R2-Q1-0069, R2-Q1-0070, R2-Q1-0072, R2-Q2-0061 and R2-Q2-0063.
0061 was not thin in ab-neg. R2-Q1-0071 gains only the registration part.
The initial exploratory comparison omitted parent-header byte costs; a second
comparison initially missed an early gate in its baseline. The figures above
are from the corrected, service-equivalent packing and gate comparison.

**Estimate:** four of the ten thin cases receive their missing source in the
lexical-only experiment; potentially **0–4 fewer thin answers** end-to-end,
depending on hybrid ranking, generation and verification. No saved answer is
changed offline and no improvement in A1 is yet established. Even fixing all
four would leave six thin answers, above the <=2% target.

## Files and validation

- `services/api/src/campus247/rag_v2/retrieval/hybrid.py`: direct RRF top-k when reranker disabled.
- `tests/rag_v2/retrieval/test_hybrid.py`: three new cases checking same-document
  clause survival, all 12 requested slots, no reranker call and scope-before-limit.
- `runs/t14_offline.py`: reproducible read-only diagnosis/comparison.
- This report: per-case evidence, provenance limits and remaining work.

Initial required command `.venv/Scripts/python.exe -B -m pytest tests/rag_v2 -q`:
**326 passed, 1 fixture setup error** (WinError 5 for the default external Temp
directory), plus two cache permission warnings. No test assertion failed.
Full rerun uses a new workspace-local `--basetemp` and disables pytest's cache
provider to preserve the existing inaccessible cache:

```text
.venv/Scripts/python.exe -B -m pytest tests/rag_v2 -q --basetemp='C:\Users\Duong Vinh\Vinh\.pytest-tmp-t14-20261030-01' -p no:cacheprovider
327 passed in 121.91s (0:02:01), exit 0
```

The offline comparison exited 0. Source/test diffs were reviewed against their
pre-T14 content hashes (both files already existed as untracked user work);
removing only the new selection block / three added cases reproduces those
hashes. Full Git status was rechecked. The two edited files preserve their
original line endings. All four task files passed the whitespace check.

Remaining: measure hybrid/end-to-end results in the separate authorized session;
improve relevance for 0071/0086; inspect run-tagged drafts/semantic verdicts for
0025/0028; address generator answer focus for A2-0015/0091. Existing debug
captures cannot settle those exact semantic decisions. No unrelated work,
datasets, expected results, thresholds, safety controls or flags were changed.
