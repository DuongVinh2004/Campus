# Load test

`evals/runners/rag_load_test.py` runs staged concurrent virtual students against the chat API.

The platform has one synthetic student account and the abuse limiter allows 30 requests/min per account, so a
single account cannot show real capacity. For a load test only, start the API with the override on its path, then
restart it normally afterwards:

```bash
CAMPUS_LOADTEST_NO_RATE_LIMIT=1 PYTHONPATH="evals/load;data/rag_v2_vendor" \
  infra/local/rag-fixture/.venv/Scripts/python.exe -B -u scripts/knowledge_platform_runtime.py start --defer-worker \
  --engine v2 --rag-v2-index data/rag_v2_index/embedded2 --frontend-name <snapshot on 3015>
python evals/runners/rag_load_test.py --stages 4,6,8 --turns 3 --out evals/results/rag-load/<name>.json
```

The runtime only reuses a running API, so stop the `knowledge_platform.py serve` processes first. A stage stops
early when more than 30 % of its turns fail, to protect the paid provider budget (each turn is about 5 provider calls).
Needs a funded provider balance; a 402 turns every answer into an error.

## What to expect (2026-11-14, one API process on this machine)

`--think-min 8 --think-max 25` is a student reading and typing between questions; the default 0-2 s is a stress test.

| simultaneous users | think time | success | p50 | p95 |
|---|---|---|---|---|
| 20 | 8-25 s | 100 % | 6.2 s | 10.9 s |
| 30 | 8-25 s | 100 % | 14.9 s | 20.3 s (at the 22 s turn budget) |
| 20 | 0-2 s | 99 % | 14.5 s | 24.8 s |

The process is CPU-bound at one core (about 60 turns/min). Before the performance work the same machine managed
6 users (p50 19 s) and failed most turns at 10.
