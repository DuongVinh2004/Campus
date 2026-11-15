"""TEST ONLY. Load-test switches for the process that imports this file (put evals/load on PYTHONPATH):

  CAMPUS_LOADTEST_NO_RATE_LIMIT=1   lift the per-account abuse limiter (one synthetic login stands in for many users)
  CAMPUS_LOADTEST_FAKE_PROVIDER=1   answer provider calls locally (no paid call); CAMPUS_LOADTEST_LEDGER_DIR gets the
                                    ledger records the gateway would have written
  CAMPUS_PROFILE_SAMPLER=<file>     sample every thread's stack every 10 ms and write a function profile to <file>

Never put this directory on PYTHONPATH of a runtime that serves real users.
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

if os.environ.get("CAMPUS_LOADTEST_NO_RATE_LIMIT") == "1":
    try:
        sys.path.insert(0, str(_ROOT / "services/api/src"))
        from campus247.presentation.middleware import abuse_limits as _al
        _al.InMemoryRateLimiterStore.check_and_increment = lambda self, key, max_requests, window_seconds: (True, max_requests, 0)
        print("LOADTEST: per-account rate limiter lifted in this process", file=sys.stderr)
    except Exception:  # noqa: BLE001 -- a missing import must never break startup
        pass

if os.environ.get("CAMPUS_LOADTEST_FAKE_PROVIDER") == "1":
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import fake_provider
        fake_provider.install(os.environ.get("CAMPUS_LOADTEST_LEDGER_DIR") or str(_ROOT / "evals/results/rag-load/fake-ledger"))
        print("LOADTEST: provider calls answered by the local fake; no paid call is made", file=sys.stderr)
    except Exception as error:  # noqa: BLE001
        print("LOADTEST: fake provider NOT installed:", type(error).__name__, error, file=sys.stderr)
        raise SystemExit("refusing to start a load-test process without the fake provider")

_cprofile_out = os.environ.get("CAMPUS_CPROFILE")
if _cprofile_out:
    # Deterministic profile of the main thread (the event loop): own time per function. Dumped every 15 s from a
    # helper thread; disabling the profiler there only affects that helper, the event loop keeps being profiled.
    import cProfile
    import threading
    import time
    _profiler = cProfile.Profile()
    _profiler.enable()

    def _dump():
        while True:
            time.sleep(15)
            try:
                _profiler.create_stats()   # stops profiling (sys.monitoring is process-wide on 3.12) ...
                _profiler.dump_stats(_cprofile_out)
            except Exception:  # noqa: BLE001
                pass
            finally:
                _profiler.enable()         # ... so turn it back on; collected data accumulate

    threading.Thread(target=_dump, daemon=True).start()

_profile_out = os.environ.get("CAMPUS_PROFILE_SAMPLER")
if _profile_out:
    import collections
    import json
    import threading
    import time

    def _sampler():
        inclusive, leaf, project_leaf = collections.Counter(), collections.Counter(), collections.Counter()
        total, me, last = 0, threading.get_ident(), time.time()
        idle = {"select", "_worker", "wait", "run_forever", "_run_once", "sleep", "accept", "_poll", "poll"}
        while True:
            time.sleep(0.01)
            for tid, frame in sys._current_frames().items():
                if tid == me:
                    continue
                if frame.f_code.co_name in idle:
                    continue
                total += 1
                leaf[f"{os.path.basename(frame.f_code.co_filename)}:{frame.f_code.co_name}"] += 1
                seen, f, innermost = set(), frame, None
                while f is not None:
                    name = f"{os.path.basename(f.f_code.co_filename)}:{f.f_code.co_name}"
                    if "campus247" in f.f_code.co_filename or "scripts" in f.f_code.co_filename:
                        seen.add(name)
                        innermost = innermost or name
                    f = f.f_back
                inclusive.update(seen)
                project_leaf[innermost or "(outside project)"] += 1
            if time.time() - last > 10:
                last = time.time()
                try:
                    with open(_profile_out, "w", encoding="utf-8") as stream:
                        json.dump({"busy_samples": total, "inclusive": inclusive.most_common(60),
                                   "leaf_any": leaf.most_common(40), "project_leaf": project_leaf.most_common(40)},
                                  stream, ensure_ascii=False)
                except OSError:
                    pass

    threading.Thread(target=_sampler, daemon=True).start()
