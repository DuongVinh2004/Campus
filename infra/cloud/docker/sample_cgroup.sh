#!/usr/bin/env bash
# Sample the container's memory and CPU while a load test runs (cgroup v2).
#   sample_cgroup.sh <seconds> <out.json>
# anon = memory that cannot be dropped under pressure (the number that decides an out-of-memory kill);
# current includes reclaimable file cache (model files read through mmap), so it is reported but is not the OOM measure.
set -euo pipefail
SECONDS_TOTAL="${1:-120}"; OUT="${2:-/tmp/cgroup.json}"
CG=/sys/fs/cgroup
limit="$(cat $CG/memory.max)"
prev_usec=$(awk '/^usage_usec/ {print $2}' $CG/cpu.stat); prev_t=$(date +%s.%N)
rows=""
for _ in $(seq 1 $((SECONDS_TOTAL / 3))); do
  sleep 3
  anon=$(awk '/^anon / {print $2}' $CG/memory.stat); file=$(awk '/^file / {print $2}' $CG/memory.stat)
  cur=$(cat $CG/memory.current); swap=$(cat $CG/memory.swap.current 2>/dev/null || echo 0)
  usec=$(awk '/^usage_usec/ {print $2}' $CG/cpu.stat); t=$(date +%s.%N)
  cpu=$(python3 -c "print(round(($usec - $prev_usec) / (($t - $prev_t) * 1e6), 2))")
  prev_usec=$usec; prev_t=$t
  rows="$rows{\"anon\":$anon,\"file\":$file,\"current\":$cur,\"swap\":$swap,\"cores\":$cpu},"
done
oom=$(awk '/^oom_kill / {print $2}' $CG/memory.events)
printf '{"limit":%s,"oom_kill":%s,"samples":[%s]}' "$limit" "$oom" "${rows%,}" > "$OUT"
python3 - "$OUT" <<'PY'
import json, sys
d = json.load(open(sys.argv[1])); s = d["samples"]; limit = int(d["limit"])
print(json.dumps({"limit_gb": round(limit / 2**30, 2), "peak_anon_gb": round(max(x["anon"] for x in s) / 2**30, 2),
                  "peak_anon_pct": round(100 * max(x["anon"] for x in s) / limit, 1),
                  "peak_current_gb": round(max(x["current"] for x in s) / 2**30, 2), "peak_swap_mb": round(max(x["swap"] for x in s) / 2**20),
                  "avg_cores": round(sum(x["cores"] for x in s) / len(s), 2), "peak_cores": max(x["cores"] for x in s), "oom_kill": d["oom_kill"]}))
PY
