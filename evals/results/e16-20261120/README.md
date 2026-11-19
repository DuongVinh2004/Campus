# E16: load test with the operations numbers beside it (2026-11-20)

Runtime restarted with the test-only switches of `evals/load` (per-account limiter lifted, provider answered by a local fake: no paid call, no real ledger entry; log lines "LOADTEST: ..." in 4 processes), then restarted normally afterwards (no switch left, scanner and worker on). Command: `rag_load_test.py --stages 20,50 --turns 3 ...` and `--stages 100 --turns 2` (the unique-question pool allows 220 turns per stage), think time 2-6 s (harder than the realistic 8-25 s).

| Stage | Turns | Success | p50 / p95 / p99 (s) | API CPU p50-p95 | API RSS max |
|---|---|---|---|---|---|
| 20 students | 60 | 100% | 5.0 / 6.4 / 6.7 | 42-194% | 549 MB |
| 50 students | 150 | 100% (14 turns were told "busy" once and retried) | 8.8 / 11.6 / 12.5 | 126-245% | 514 MB |
| 100 students | 200 | **90.5%** (19 turns gave up after repeated busy 503, admission limit 24 in flight) | 10.2 / 13.1 / 14.0 | 105-213% | 560 MB |

Operations page (`/v1/admin/operations/status`, saved here) after the 100-student stage: 181 turns in the last 5 minutes, 172 ok + 9 abstained, error rate 0 -- the same 181 HTTP 200 responses the load tool counted; admission rejections 206 (the tool counted 225 refusals including retries inside its own window); p95 reported as "<= 20 s" (a histogram bucket bound; the tool measured 13.1 s, consistent); one event-loop block of 1.4 s in 5 minutes (2.9 s max in the hour, during restarts). The page's quality tile shows the first nightly retrieval result (any 99.2%, top 8 96.7%, survive rerank 87.5%).

Design criteria: counts match exactly; p95 consistent with the bucket; the alert rules did not fire a quality alert. Not measured: the alert engine under a deliberately induced overload (no Telegram/email channel configured), and a realistic think time at 100 students (earlier phase 1 numbers: 99.5%, p95 ~13 s).

**Mistake to report:** the first attempt started the runtime with an absolute POSIX path in PYTHONPATH, so the load-test switches were NOT loaded; the run made **65 real calls to the paid provider** (accounting-only gateway, recorded in the real ledger `infra/local/public-rag-20261013`) and the limiter answered 29 of 44 turns with errors. It was noticed from the gateway log, the runtime was restarted with the relative PYTHONPATH from `evals/load/README.md`, and the numbers above are from the second, fake-provider run. Always check for the 4 "LOADTEST" lines before a run.
