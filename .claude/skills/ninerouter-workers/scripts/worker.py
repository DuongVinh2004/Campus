#!/usr/bin/env python3
"""Dispatch ONE task to a 9router (Antigravity) worker and save the result.

The worker only ever returns text. It has no tools, no filesystem and no shell, so it
cannot change anything by itself; file changes go through guard.py and the supervisor.

  python -I worker.py --id ui-btn --brief brief.md --context apps/web/src/components/Toast.tsx \
      --mode files --allow "apps/web/src/components/Toast*.tsx"
  python -I worker.py --id scout --brief-text "Liệt kê ..." --context "apps/web/src/app/**/page.tsx" --mode json --verify-quotes

Prints a compact summary (keeps the supervisor's context small); full output is in the run dir.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NEVER_SEND, REPO, RUNS_DIR, deny_hit, load_config, match_any, norm, redact, safe_rel  # noqa: E402

CONTRACT = """You are a WORKER in a supervised software pipeline. A lead engineer (the supervisor) assigns you exactly one task and reviews everything you return. Absolute rules:
1. Do exactly what the brief says, nothing more. No extra features, no refactors, renames, reformatting or "improvements" outside the stated scope.
2. You have NO tools, NO filesystem, NO shell and NO network. Never claim you ran, tested, saved or verified anything.
3. Never write code that deletes files or data, drops/truncates/deletes database rows, runs git or shell commands, spawns processes, changes authentication/authorization/security checks, reads or writes secrets, or calls external services. If the task cannot be done without that, output only: BLOCKED: <one-line reason>.
4. Do not invent APIs, props, functions, endpoints or imports you were not shown in the context. If something essential is missing, put `QUESTION: <what is missing>` as the first line, then do everything you can without it.
5. Follow the conventions visible in the context: code style, existing imports, data-testid attributes, accessibility attributes, and Vietnamese (vi-VN) user-facing text.
6. Keep every existing data-testid, aria-* attribute, prop, export and test unless the brief explicitly says to change it.
7. Output ONLY the required format below. No greeting, no preamble, no closing remarks.
"""

FORMATS = {
    "text": "OUTPUT FORMAT: concise Markdown answer. Prefer bullet points and `path:line` citations. At most {words} words unless the brief says otherwise.",
    "json": "OUTPUT FORMAT: a single valid JSON value only (no Markdown fences, no comments), matching the schema in the brief.{quotes}",
    "files": """OUTPUT FORMAT: for every file you create or change, output its COMPLETE new content:
=== FILE: relative/path/from/repo/root ===
<entire file content>
=== END FILE ===
Never output diffs, ellipses, "...", "rest unchanged" or partial files. Never delete a file. Only these paths may be written: {allow}.
After the files, output:
=== NOTES ===
- at most 5 short bullets: what changed, assumptions, what the supervisor should check
=== END NOTES ===""",
    "edit": """OUTPUT FORMAT: targeted edits. For each existing file you change, output one or more blocks:
=== EDIT: relative/path/from/repo/root ===
<<<<<<< SEARCH
exact lines copied from the current file (without the line-number prefix), enough lines to be unique
=======
the replacement lines
>>>>>>> REPLACE
=== END EDIT ===
Each SEARCH must match the current file exactly once; keep SEARCH short (3-15 lines). Several SEARCH/REPLACE pairs may sit in one EDIT block, applied top to bottom. For a brand-new file use a full block instead:
=== FILE: relative/path ===
<entire content>
=== END FILE ===
Never delete a file. Only these paths may be written: {allow}.
After the edits, output:
=== NOTES ===
- at most 5 short bullets: what changed, assumptions, what the supervisor should check
=== END NOTES ===""",
}
QUOTES_RULE = ' Every finding object MUST include "path", "line" (1-based) and "quote" (an exact substring copied from that line of the context, 5-120 chars). The supervisor verifies quotes by code; invented quotes are rejected.'

FILE_BLOCK = re.compile(r"^=== FILE: (?P<path>.+?) ===\r?\n(?P<body>.*?)^=== END FILE ===", re.M | re.S)
EDIT_BLOCK = re.compile(r"^=== EDIT: (?P<path>.+?) ===\r?\n(?P<body>.*?)^=== END EDIT ===", re.M | re.S)
SR_PAIR = re.compile(r"^<<<<<<< SEARCH\r?\n(?P<search>.*?)^=======\r?\n(?P<replace>.*?)^>>>>>>> REPLACE\s*$", re.M | re.S)
LINE_PREFIX = re.compile(r"^\s{0,6}\d{1,5}\| ?", re.M)


def apply_edits(original: str, body: str) -> tuple[str, list[str]]:
    """Apply SEARCH/REPLACE pairs to text. Exact match first, then a whitespace-tolerant match."""
    text, errors = original, []
    pairs = list(SR_PAIR.finditer(body))
    if not pairs:
        return text, ["EDIT block without SEARCH/REPLACE pairs"]
    for n, m in enumerate(pairs, 1):
        search, replace = m.group("search"), m.group("replace")
        if LINE_PREFIX.search(search) and all(LINE_PREFIX.match(l) for l in search.splitlines() if l.strip()):
            search = LINE_PREFIX.sub("", search)  # worker copied the context line numbers
        if not search.strip():
            errors.append(f"edit #{n}: empty SEARCH")
            continue
        count = text.count(search)
        if count == 1:
            text = text.replace(search, replace, 1)
            continue
        if count > 1:
            errors.append(f"edit #{n}: SEARCH matches {count} places, needs more context")
            continue
        # tolerant: compare lines with trailing whitespace stripped and common indentation ignored
        lines, s_lines = text.split("\n"), [l.rstrip() for l in search.rstrip("\n").split("\n")]
        hits = [i for i in range(len(lines) - len(s_lines) + 1)
                if [l.rstrip().strip() for l in lines[i:i + len(s_lines)]] == [l.strip() for l in s_lines]]
        if len(hits) == 1:
            i = hits[0]
            rep = replace[:-1] if replace.endswith("\n") else replace
            lines[i:i + len(s_lines)] = rep.split("\n") if rep else []
            text = "\n".join(lines)
        else:
            errors.append(f"edit #{n}: SEARCH not found" if not hits else f"edit #{n}: SEARCH ambiguous ({len(hits)} fuzzy matches)")
    return text, errors
NOTES_BLOCK = re.compile(r"^=== NOTES ===\r?\n(?P<body>.*?)(^=== END NOTES ===|\Z)", re.M | re.S)


def pack_context(specs: list[str], max_file_kb: int, max_total_kb: int) -> tuple[str, list[str], list[str], list[str]]:
    """Return (context text, included labels, warnings, repo paths sent in full). Spec: path | glob | path:START-END."""
    parts, included, warns, full, total = [], [], [], [], 0
    for spec in specs:
        m = re.match(r"^(.*?):(\d+)-(\d+)$", spec)
        rng = (int(m.group(2)), int(m.group(3))) if m else None
        pattern = m.group(1) if m else spec
        base = Path(pattern) if Path(pattern).is_absolute() else REPO / pattern
        matches = sorted(glob.glob(str(base), recursive=True)) or [str(base)]
        tmp_root = Path(tempfile.gettempdir()).resolve()
        for path in matches:
            p = Path(path).resolve()
            try:
                checked = safe_rel(p.relative_to(REPO.resolve()).as_posix())
            except ValueError:
                # outside the repo: only temp files (logs/outputs saved to the scratchpad) may be sent
                checked = f"tmp/{p.name}" if p.is_relative_to(tmp_root) else None
            if checked is None:
                warns.append(f"skip (outside repo): {pattern}")
                continue
            rel = checked.split("\0")[0]
            if deny_hit(checked, NEVER_SEND) or match_any(p.name, NEVER_SEND):
                warns.append(f"skip (never send): {rel}")
                continue
            if not p.is_file():
                warns.append(f"skip (missing): {rel}")
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            start = 1
            if rng:
                start = max(1, rng[0])
                lines = lines[start - 1 : rng[1]]
            text, n = redact("\n".join(lines))
            complete = not rng and not n
            if n:
                warns.append(f"redacted {n} secret-like value(s) in {rel} (file cannot be rewritten whole)")
            if len(text.encode()) > max_file_kb * 1024:
                text = text.encode()[: max_file_kb * 1024].decode("utf-8", "ignore")
                warns.append(f"truncated {rel} to {max_file_kb} KB")
                complete = False
            if total + len(text) > max_total_kb * 1024:
                warns.append(f"skip (total context cap {max_total_kb} KB): {rel}")
                continue
            total += len(text)
            if complete and not rel.startswith("tmp/"):
                full.append(rel)
            label = f"{rel}" + (f" (lines {start}-{start + len(lines) - 1})" if rng else "")
            numbered = "\n".join(f"{start + i:>5}| {ln}" for i, ln in enumerate(text.splitlines()))
            parts.append(f"<<< CONTEXT FILE: {label} — each line is prefixed by its line number and '| ', which is NOT part of the file >>>\n{numbered}\n<<< END CONTEXT FILE >>>")
            included.append(label)
    return "\n\n".join(parts), included, warns, full


def call_router(cfg: dict, model: str, messages: list[dict], max_tokens: int, timeout: int, temperature: float) -> tuple[str, dict]:
    body = {"model": model, "messages": messages, "stream": True, "temperature": temperature}
    if max_tokens:
        body["max_tokens"] = max_tokens
    req = urllib.request.Request(
        cfg["NINEROUTER_BASE_URL"].rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {cfg['NINEROUTER_API_KEY']}", "Content-Type": "application/json"},
    )
    out, usage, served = [], {}, model
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            if chunk.get("error"):
                raise RuntimeError(f"router error: {str(chunk['error'])[:300]}")
            served = chunk.get("model", served)
            usage = chunk.get("usage") or usage
            for ch in chunk.get("choices", []):
                piece = (ch.get("delta") or {}).get("content")
                if piece:
                    out.append(piece)
    return "".join(out), {"usage": usage, "served_model": served}


def strip_fences(text: str) -> str:
    t = text.strip()
    m = re.match(r"^```[a-zA-Z0-9]*\s*\n(.*)\n```\s*$", t, re.S)
    return m.group(1) if m else t


def verify_quotes(data, ctx_specs: list[str]) -> list[str]:
    """Check every {path,line,quote} finding against the real file (±3 lines)."""
    bad = []
    items = data if isinstance(data, list) else data.get("findings", []) if isinstance(data, dict) else []
    for i, it in enumerate(items):
        if not isinstance(it, dict) or "quote" not in it:
            continue
        rel = (safe_rel(str(it.get("path", ""))) or "").split("\0")[0] or None
        q = str(it.get("quote", "")).strip()
        if not rel or not (REPO / rel).is_file() or not q:
            bad.append(f"#{i}: bad path/quote {it.get('path')!r}")
            it["_verified"] = False
            continue
        lines = (REPO / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        try:
            ln = int(it.get("line", 0))
        except (TypeError, ValueError):
            ln = 0
        window = lines[max(0, ln - 4) : ln + 3] if ln > 0 else lines
        ok = any(q in w for w in window) or (ln <= 0 and q in "\n".join(lines))
        it["_verified"] = ok
        if not ok:
            bad.append(f"#{i}: quote not found near {rel}:{ln}")
    return bad


def run_job(job: dict, cfg: dict | None = None, quiet: bool = False) -> dict:
    cfg = cfg or load_config()
    prev = Path(job["followup"]) if job.get("followup") else None
    prev_meta = json.loads((prev / "meta.json").read_text(encoding="utf-8")) if prev else {}
    jid = re.sub(r"[^A-Za-z0-9_.-]", "-", job.get("id") or prev_meta.get("id", "job") + "-fix")[:60]
    mode = job.get("mode") or prev_meta.get("mode") or "text"
    allow = [norm(a) for a in (job.get("allow") or prev_meta.get("allow") or [])]
    if mode in ("files", "edit") and not allow:
        raise SystemExit(f"--mode {mode} requires at least one --allow glob")
    brief = job.get("brief_text") or ""
    if job.get("brief"):
        bp = Path(job["brief"])
        brief = (bp if bp.is_absolute() else REPO / bp).read_text(encoding="utf-8")
    brief, nb = redact(brief)
    ctx, included, warns, full = pack_context(job.get("context", []), job.get("max_file_kb", 120), job.get("max_total_kb", 900))
    if nb:
        warns.append(f"redacted {nb} secret-like value(s) in brief")

    fmt = FORMATS[mode].format(words=job.get("words", 400), allow=", ".join(allow) or "(none)",
                               quotes=QUOTES_RULE if job.get("verify_quotes") else "")
    system = CONTRACT + "\n" + fmt
    if prev:
        # Follow-up: same conversation, plus the supervisor's correction and the guard findings.
        messages = json.loads((prev / "messages.json").read_text(encoding="utf-8"))
        messages.append({"role": "assistant", "content": (prev / "response.md").read_text(encoding="utf-8")})
        findings = []
        if (prev / "check.json").exists():
            findings = json.loads((prev / "check.json").read_text(encoding="utf-8")).get("blocking", [])
        full = sorted(set(full) | set(prev_meta.get("full_context", [])))
        included = prev_meta.get("context", []) + included
        fb = "\n".join(f"- {f}" for f in findings) or "- (none)"
        user = (f"# SUPERVISOR FEEDBACK — fix exactly this, change nothing else\n{brief.strip()}\n\n"
                f"# GUARD FINDINGS ON YOUR PREVIOUS ANSWER\n{fb}\n\n"
                + (f"# UPDATED CONTEXT\n{ctx}\n\n" if ctx else "# The files are unchanged since your previous answer.\n\n")
                + f"# Output your COMPLETE answer again in the required format.\n{fmt}")
        messages.append({"role": "user", "content": user})
    else:
        user = f"# TASK BRIEF\n{brief.strip()}\n\n# CONTEXT\n{ctx or '(none)'}\n\n# REMINDER\n{fmt}"
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run = RUNS_DIR / f"{stamp}-{jid}"
    n = 1
    while run.exists():
        n += 1
        run = RUNS_DIR / f"{stamp}-{jid}-{n}"
    run.mkdir(parents=True)
    (run / "prompt.md").write_text(f"## SYSTEM\n{system}\n\n## USER\n{user}", encoding="utf-8")
    (run / "messages.json").write_text(json.dumps(messages, ensure_ascii=False), encoding="utf-8")

    model = job.get("model") or prev_meta.get("model") or cfg.get("NINEROUTER_MODEL")
    meta = {"id": jid, "mode": mode, "model": model, "allow": allow, "context": included, "full_context": full,
            "warnings": warns, "repo": str(REPO), "created": stamp, "attempts": 0, "status": "error",
            "followup_of": str(prev) if prev else None}
    text, err, t0 = "", None, time.monotonic()
    for attempt in range(job.get("retries", 2) + 1):
        meta["attempts"] = attempt + 1
        try:
            text, info = call_router(cfg, model, messages, job.get("max_tokens", 60000), job.get("timeout", 600), job.get("temperature", 0.2))
            meta.update(info)
            if text.strip():
                err = None
                break
            err = "empty response"
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}: {e.read()[:300].decode('utf-8', 'replace')}"
            if e.code in (400, 401, 403, 404):
                break
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"[:400]
        time.sleep(min(30, 3 * (attempt + 1) ** 2))
    meta["latency_s"] = round(time.monotonic() - t0, 1)
    (run / "response.md").write_text(text, encoding="utf-8")

    summary = {"run": str(run), "id": jid, "mode": mode}
    if err:
        meta["status"], meta["error"] = "error", err
    else:
        first = text.lstrip().splitlines()[0] if text.strip() else ""
        meta["status"] = "blocked" if first.startswith("BLOCKED:") else "question" if first.startswith("QUESTION:") else "ok"
        if meta["status"] != "ok":
            summary["worker_says"] = first[:300]
        if mode in ("files", "edit"):
            files: dict[str, dict] = {}
            for m in FILE_BLOCK.finditer(text):
                files[norm(m.group("path"))] = {"content": m.group("body"), "errors": [], "kind": "file"}
            if mode == "edit":
                for m in EDIT_BLOCK.finditer(text):
                    rel = norm(m.group("path"))
                    checked = safe_rel(rel)
                    target = REPO / checked.split("\0")[0] if checked else None
                    if rel in files:  # several EDIT blocks for one file: apply on top of the previous result
                        base, errs = files[rel]["content"], files[rel]["errors"]
                    elif target and target.is_file():
                        base, errs = target.read_bytes().decode("utf-8", "replace").replace("\r\n", "\n"), []
                    else:
                        files[rel] = {"content": None, "errors": ["EDIT on a file that does not exist (use a FILE block)"]}
                        continue
                    new, e = apply_edits(base, m.group("body"))
                    files[rel] = {"content": new, "errors": errs + e, "kind": files.get(rel, {}).get("kind", "edit")}
            notes = NOTES_BLOCK.search(text)
            meta["notes"] = notes.group("body").strip()[:1500] if notes else ""
            stash = run / "files"
            stash.mkdir(exist_ok=True)
            listing = []
            for rel, f in files.items():
                item = {"path": rel, "blob": None, "edit_errors": f["errors"], "kind": f.get("kind", "edit")}
                if f["content"] is not None:
                    key = hashlib.sha1(rel.encode()).hexdigest()[:10]
                    (stash / f"{key}.txt").write_text(f["content"], encoding="utf-8")
                    item["blob"] = f"files/{key}.txt"
                listing.append(item)
            (run / "files.json").write_text(json.dumps(listing, ensure_ascii=False, indent=1), encoding="utf-8")
            if not files and meta["status"] == "ok":
                meta["status"], meta["error"] = "error", "no FILE/EDIT blocks in response"
            else:
                from guard import check_run  # local import: guard depends on worker output
                (run / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
                g = check_run(run)
                summary["guard"] = g
                if g["blocking"]:
                    meta["status"] = "guard_blocked"
            if meta.get("notes"):
                summary["notes"] = meta["notes"]
        elif mode == "json":
            try:
                data = json.loads(strip_fences(text))
                if job.get("verify_quotes"):
                    bad = verify_quotes(data, job.get("context", []))
                    summary["quote_check"] = {"failed": len(bad), "examples": bad[:5]}
                (run / "result.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
                summary["result"] = str(run / "result.json")
            except json.JSONDecodeError as e:
                meta["status"], meta["error"] = "error", f"invalid JSON: {e}"
        limit = job.get("print_limit", 2500)
        if mode in ("text", "json") and not quiet:
            body = text.strip()
            summary["output"] = body if len(body) <= limit else body[:limit] + f"\n…[{len(body) - limit} more chars in response.md]"
    summary.update({k: meta[k] for k in ("status", "attempts", "latency_s") if k in meta})
    if meta.get("error"):
        summary["error"] = meta["error"]
    if warns:
        summary["warnings"] = warns
    u = meta.get("usage") or {}
    if u:
        summary["tokens"] = f"{u.get('prompt_tokens', '?')} in / {u.get('completion_tokens', '?')} out"
    (run / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


def print_summary(s: dict) -> None:
    out = {k: v for k, v in s.items() if k != "output"}
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if "output" in s:
        print("----- worker output -----")
        print(s["output"])


def ping() -> int:
    """Fast health check (no model call): router reachable, key accepted, default model listed."""
    cfg = load_config()
    base = cfg["NINEROUTER_BASE_URL"].rstrip("/")
    hdr = {"Authorization": f"Bearer {cfg['NINEROUTER_API_KEY']}"}
    try:
        with urllib.request.urlopen(urllib.request.Request(base + "/models", headers=hdr), timeout=10) as r:
            ids = [m.get("id") for m in json.loads(r.read()).get("data", [])]
        # key check without generating: a malformed body is rejected after auth (4xx other than 401/403 = key ok)
        req = urllib.request.Request(base + "/chat/completions", data=b"{}", headers={**hdr, "Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=15).close()
            key = "ok"
        except urllib.error.HTTPError as e:
            key = "rejected" if e.code in (401, 403) else "ok"
    except Exception as e:  # noqa: BLE001
        print(f"9router DOWN: {type(e).__name__}: {e}")
        return 1
    want = cfg.get("NINEROUTER_MODEL")
    print(f"9router up: {len(ids)} models; key {key}; {want} {'listed' if want in ids else 'NOT listed'}")
    return 0 if key == "ok" and want in ids else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--brief", help="brief file (repo-relative or absolute)")
    g.add_argument("--brief-text")
    ap.add_argument("--followup", metavar="RUN_DIR", help="continue that run's conversation with a correction (brief = feedback)")
    ap.add_argument("--ping", action="store_true", help="check 9router is up and the key works, then exit")
    ap.add_argument("--context", action="append", default=[], help="path | glob | path:START-END (repeatable)")
    ap.add_argument("--mode", choices=["text", "json", "files", "edit"], help="default text (followup: inherited)")
    ap.add_argument("--allow", action="append", default=[], help="glob the worker may write (files mode)")
    ap.add_argument("--model")
    ap.add_argument("--verify-quotes", action="store_true")
    ap.add_argument("--words", type=int, default=400)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--print-limit", type=int, default=2500)
    a = ap.parse_args()
    if a.ping:
        return ping()
    if not (a.brief or a.brief_text):
        ap.error("--brief or --brief-text is required")
    job = {"id": a.id, "followup": a.followup, "brief": a.brief, "brief_text": a.brief_text, "context": a.context, "mode": a.mode,
           "allow": a.allow, "model": a.model, "verify_quotes": a.verify_quotes, "words": a.words,
           "retries": a.retries, "timeout": a.timeout, "print_limit": a.print_limit}
    s = run_job(job)
    print_summary(s)
    return 0 if s.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
