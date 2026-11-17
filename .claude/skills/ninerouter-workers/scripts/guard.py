#!/usr/bin/env python3
"""Gate between a worker's output and the repo. The supervisor decides; this enforces.

  python -I guard.py check  RUN_DIR            # policy check + changes.patch (no writes to repo)
  python -I guard.py diff   RUN_DIR [--path P] # print the unified diff (optionally one file)
  python -I guard.py apply  RUN_DIR [--only P] # write files: only if check passes and targets unchanged
  python -I guard.py revert RUN_DIR            # undo an apply (only files untouched since)

Nothing here ever deletes user data: apply backs up every original into the run dir;
revert only removes a file the worker itself created and nobody edited afterwards.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DANGER_RE, HARD_DENY, REPO, SECRET_RE, WARN_ONLY, deny_hit, match_any, safe_rel  # noqa: E402

MAX_BYTES = 300 * 1024


def sha(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data is not None else None


def read_bytes(p: Path) -> bytes | None:
    return p.read_bytes() if p.is_file() else None


def check_run(run: Path) -> dict:
    run = Path(run)
    meta = json.loads((run / "meta.json").read_text(encoding="utf-8")) if (run / "meta.json").exists() else {}
    allow = meta.get("allow", [])
    listing = json.loads((run / "files.json").read_text(encoding="utf-8"))
    prior = {}
    if (run / "check.json").exists():
        prior = {f["path"]: f for f in json.loads((run / "check.json").read_text(encoding="utf-8"))["files"]}
    blocking, warnings, files, patch = [], [], [], []
    seen = set()
    for item in listing:
        raw_path = item["path"]
        checked = safe_rel(raw_path)
        if checked is None:
            blocking.append(f"{raw_path!r}: unsafe path (escapes repo or Windows alias trick)")
            continue
        rel = checked.split("\0")[0]
        if rel.lower() in seen:
            blocking.append(f"{rel}: emitted twice")
            continue
        seen.add(rel.lower())
        if deny_hit(checked, HARD_DENY):
            blocking.append(f"{rel}: hard-denied path (core logic / data / config / secrets)")
            continue
        if not all(match_any(p, allow) for p in checked.split("\0")):
            blocking.append(f"{rel}: not in --allow {allow}")
            continue
        for e in item.get("edit_errors", []):
            blocking.append(f"{rel}: {e}")
        target = REPO / rel
        old_b = read_bytes(target)
        if (old_b is not None and item.get("kind", "file") == "file"
                and rel.lower() not in {c.lower() for c in meta.get("full_context", [])}):
            blocking.append(f"{rel}: worker rewrote an existing file it did not see in full (send it in --context or use --mode edit)")
        if item.get("blob") is None:
            continue
        new = (run / item["blob"]).read_text(encoding="utf-8")
        old = old_b.decode("utf-8", "replace").replace("\r\n", "\n") if old_b is not None else ""
        if len(new.encode()) > MAX_BYTES:
            blocking.append(f"{rel}: file too large ({len(new.encode())} B)")
        if not new.strip():
            blocking.append(f"{rel}: empty content (would wipe the file)")
        old_l, new_l = old.splitlines(), new.splitlines()
        sm = difflib.SequenceMatcher(a=old_l, b=new_l, autojunk=False)
        added, removed = [], []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag in ("replace", "delete"):
                removed += old_l[i1:i2]
            if tag in ("replace", "insert"):
                added += new_l[j1:j2]
        added_txt = "\n".join(added)
        for rx, why in DANGER_RE:
            m = rx.search(added_txt)
            if m:
                (warnings if why in WARN_ONLY else blocking).append(f"{rel}: {why}: {m.group(0)[:60]!r}")
        if SECRET_RE.search(added_txt):
            blocking.append(f"{rel}: secret-like value in added lines")
        if old_b is not None and ((len(old_l) > 40 and len(new_l) < 0.6 * len(old_l))
                                  or (len(old_l) >= 5 and len(new_l) < 0.3 * len(old_l))):
            blocking.append(f"{rel}: shrinks {len(old_l)} -> {len(new_l)} lines (likely truncated/removal)")
        for attr in ("export ", "data-testid", "aria-"):
            lost = sum(l.count(attr) for l in removed) - sum(l.count(attr) for l in added)
            if lost > 0:
                msg = f"{rel}: {lost} fewer `{attr}` occurrence(s)"
                (blocking if attr == "export " and not meta.get("allow_export_removal") else warnings).append(msg)
        orig = prior.get(rel, {}).get("orig_sha", sha(old_b))
        files.append({"path": rel, "new_file": old_b is None, "added": len(added), "removed": len(removed),
                      "orig_sha": orig, "blob": item["blob"], "crlf": bool(old_b and b"\r\n" in old_b)})
        patch += difflib.unified_diff(old_l, new_l, f"a/{rel}", f"b/{rel}", lineterm="")
    (run / "changes.patch").write_text("\n".join(patch) + "\n", encoding="utf-8")
    result = {"files": files, "blocking": blocking, "warnings": warnings}
    (run / "check.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"files": [f"{f['path']} (+{f['added']} -{f['removed']}{', new' if f['new_file'] else ''})" for f in files],
            "blocking": blocking, "warnings": warnings, "patch": str(run / "changes.patch")}


def apply_run(run: Path, only: list[str]) -> dict:
    res = check_run(run)
    chk = json.loads((run / "check.json").read_text(encoding="utf-8"))
    todo = [f for f in chk["files"] if not only or f["path"] in only]
    # With --only, findings on other files do not stop the clean ones (partial apply after review).
    relevant = res["blocking"] if not only else [b for b in res["blocking"] if any(b.startswith(p + ":") for p in only)
                                                  or not any(b.startswith(f["path"] + ":") for f in chk["files"])]
    if relevant or not todo:
        return {"applied": [], "refused": "guard blocking findings" if relevant else "nothing to apply", "blocking": relevant}
    stale = [f["path"] for f in todo if sha(read_bytes(REPO / f["path"])) != f["orig_sha"]]
    if stale:
        return {"applied": [], "refused": "target changed since worker run; re-dispatch with fresh context", "stale": stale}
    backup = run / "backup"
    backup.mkdir(exist_ok=True)
    applied = []
    for f in todo:
        target = REPO / f["path"]
        old_b = read_bytes(target)
        key = hashlib.sha1(f["path"].encode()).hexdigest()[:10]
        if old_b is not None:
            (backup / f"{key}.orig").write_bytes(old_b)
        text = (run / f["blob"]).read_text(encoding="utf-8").replace("\r\n", "\n")
        if not text.endswith("\n"):
            text += "\n"
        data = (text.replace("\n", "\r\n") if f["crlf"] else text).encode("utf-8")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        applied.append({"path": f["path"], "new_file": old_b is None, "backup": f"backup/{key}.orig" if old_b is not None else None,
                        "applied_sha": sha(data)})
    prev = json.loads((run / "applied.json").read_text(encoding="utf-8")) if (run / "applied.json").exists() else []
    (run / "applied.json").write_text(json.dumps(prev + applied, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"applied": [a["path"] for a in applied], "warnings": res["warnings"]}


def revert_run(run: Path) -> dict:
    path = run / "applied.json"
    if not path.exists():
        return {"reverted": [], "note": "nothing applied"}
    done, skipped = [], []
    for a in reversed(json.loads(path.read_text(encoding="utf-8"))):
        target = REPO / a["path"]
        if sha(read_bytes(target)) != a["applied_sha"]:
            skipped.append(f"{a['path']}: edited after apply, left as is")
            continue
        if a["backup"]:
            target.write_bytes((run / a["backup"]).read_bytes())
        else:
            target.unlink()  # a file this worker run created and nobody touched since
        done.append(a["path"])
    if not skipped:
        path.rename(run / "applied.reverted.json")
    return {"reverted": done, "skipped": skipped}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["check", "diff", "apply", "revert"])
    ap.add_argument("run")
    ap.add_argument("--path")
    ap.add_argument("--only", action="append", default=[])
    a = ap.parse_args()
    run = Path(a.run)
    sys.stdout.reconfigure(encoding="utf-8")
    if a.cmd == "check":
        r = check_run(run)
    elif a.cmd == "diff":
        check_run(run)
        text = (run / "changes.patch").read_text(encoding="utf-8")
        if a.path:
            chunks = text.split("--- a/")
            text = "".join("--- a/" + c for c in chunks if c.startswith(a.path + "\n"))
        print(text)
        return 0
    elif a.cmd == "apply":
        r = apply_run(run, a.only)
    else:
        r = revert_run(run)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if not r.get("blocking") and not r.get("refused") else 2


if __name__ == "__main__":
    raise SystemExit(main())
