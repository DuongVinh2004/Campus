#!/usr/bin/env python3
"""Drive the front-end variant workers to a working result with no supervisor tokens.

For each variant: take the worker's latest run, apply it with guard.py, start the variant server, run the browser
acceptance check (scripts/fe_variant_check.mjs), and when something fails send the exact problems back to the same
worker as a follow-up. At most MAX_FIX follow-ups per variant; after that the variant is reported as "needs a human".
When a variant passes, screenshots are taken (scripts/fe_variant_shots.mjs) into infra/local/ui-shots/variants/<name>/.

  python -I scripts/fe_variant_loop.py atelier:3101 conversation:3102 bento:3103 pocket:3104
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / ".claude/skills/ninerouter-workers/scripts"
sys.path.insert(0, str(SKILL))
from common import RUNS_DIR, load_config  # noqa: E402
from guard import apply_run  # noqa: E402
from worker import run_job  # noqa: E402

MAX_FIX = 3
STATUS = REPO / "infra/local/ui-shots/variants/status.json"
lock = threading.Lock()
check_lock = threading.Lock()  # one browser check at a time: less RAM and no API rate-limit clashes between variants
state: dict[str, dict] = {}


def log(name: str, msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {name}: {msg}"
    print(line, flush=True)
    with lock:
        state.setdefault(name, {})["last"] = msg
        STATUS.parent.mkdir(parents=True, exist_ok=True)
        STATUS.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def latest_run(name: str, any_generation: bool = False) -> Path:
    runs = sorted(p for p in RUNS_DIR.iterdir() if (f"-fe-{name}" in p.name if any_generation else p.name.endswith(f"-fe-{name}")))
    if not runs:
        raise SystemExit(f"no worker run found for fe-{name}")
    return runs[-1]


def server_up(port: int) -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/shared/api.js", timeout=3).read(10)
        return True
    except Exception:  # noqa: BLE001
        return False


def ensure_server(name: str, port: int) -> None:
    if server_up(port):
        return
    subprocess.Popen(["node", "scripts/fe_variant_server.mjs", name, str(port)], cwd=REPO,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
    for _ in range(20):
        time.sleep(0.5)
        if server_up(port):
            return
    raise RuntimeError("variant server did not start")


def browser_check(name: str, port: int) -> dict:
  with check_lock:
    proc = subprocess.run(["node", "scripts/fe_variant_check.mjs", name, str(port)], cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", timeout=420)
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        return {"ok": False, "problems": [f"the check script itself failed: {(proc.stderr or proc.stdout)[-400:]}"]}


def followup(name: str, run: Path, feedback: str, cfg: dict) -> Path:
    brief = (
        f"You have FULL authority over everything inside fe-variants/{name}/ (add, rename or rewrite any file there, and split code "
        "into more files if that helps). An automated browser check (Playwright, desktop 1360px and mobile 390px, signed in as a real "
        "student against the real API) found the problems below. Fix every one of them for real, keep the design direction and "
        "everything that already works, and answer with SEARCH/REPLACE edit blocks (edit mode) for the existing files, never re-print a whole large file; use a FILE block only for a brand-new file.\n\nPROBLEMS:\n" + feedback)
    summary = run_job({"followup": str(run), "brief_text": brief, "context": [f"fe-variants/{name}/**", "fe-variants/_shared/api.js"],
                       "max_tokens": 64000, "timeout": 1500, "mode": "edit"}, cfg, True)
    return Path(summary["run"])


def drive(name: str, port: int, cfg: dict, resume: bool = False) -> None:
    run = latest_run(name, any_generation=resume)
    skip_apply = resume
    for _ in range(0 if resume else 360):  # the first-round job may still be running: wait up to 30 minutes for its result
        if (run / "response.md").exists():
            time.sleep(20)  # let the worker finish parsing and writing meta.json
            break
        time.sleep(5)
    fixes = 0
    while True:
        meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
        feedback = ""
        if skip_apply:
            skip_apply = False
            ensure_server(name, port)
            report = browser_check(name, port)
            if report["ok"]:
                log(name, "PASSED the browser check; taking screenshots")
                subprocess.run(["node", "scripts/fe_variant_shots.mjs", name, str(port)], cwd=REPO, capture_output=True, timeout=600)
                state.setdefault(name, {})["result"] = "passed on resume"
                return
            feedback = chr(10).join(f"- {p}" for p in report["problems"])
        elif meta.get("status") != "ok":
            chk = run / "check.json"
            blocking = json.loads(chk.read_text(encoding="utf-8")).get("blocking", []) if chk.exists() else []
            feedback = "Your previous answer was rejected: " + (meta.get("error") or "") + "\n" + "\n".join(f"- {b}" for b in blocking)
        else:
            res = apply_run(run, [])
            if not res.get("applied"):
                feedback = f"Your files could not be applied: {json.dumps(res, ensure_ascii=False)[:1500]}"
            else:
                log(name, f"applied {len(res['applied'])} file(s); running the browser check")
                ensure_server(name, port)
                report = browser_check(name, port)
                if report["ok"]:
                    log(name, "PASSED the browser check; taking screenshots")
                    subprocess.run(["node", "scripts/fe_variant_shots.mjs", name, str(port)], cwd=REPO, capture_output=True, timeout=600)
                    state.setdefault(name, {})["result"] = f"passed after {fixes} fix round(s)"
                    log(name, state[name]["result"])
                    return
                feedback = "\n".join(f"- {p}" for p in report["problems"])
        if fixes >= MAX_FIX:
            state.setdefault(name, {})["result"] = f"NEEDS HUMAN after {fixes} fix rounds"
            log(name, f"gave up after {fixes} fix rounds; last problems:\n{feedback[:1500]}")
            (STATUS.parent / f"{name}-last-problems.txt").write_text(feedback, encoding="utf-8")
            return
        fixes += 1
        log(name, f"fix round {fixes}/{MAX_FIX}: sending {feedback.count(chr(10)) + 1} problem line(s) to the worker")
        try:
            run = followup(name, run, feedback, cfg)
        except Exception as exc:  # noqa: BLE001
            log(name, f"follow-up call failed: {type(exc).__name__}: {str(exc)[:200]}")
            time.sleep(5)


def main() -> int:
    cfg = load_config()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    resume = "--resume" in sys.argv
    targets = [(a.split(":")[0], int(a.split(":")[1])) for a in args]
    threads = [threading.Thread(target=drive, args=(n, p, cfg, resume), name=n) for n, p in targets]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(json.dumps({k: v.get("result", "?") for k, v in state.items()}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
