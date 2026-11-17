"""Offline self-test of the guard/edit policy (no model call). Run: python -I selftest.py"""
import json, shutil, sys, tempfile
from pathlib import Path

S = Path(__file__).resolve().parent
sys.path.insert(0, str(S))
from common import safe_rel, deny_hit, HARD_DENY, match_any  # noqa
from worker import apply_edits  # noqa
from guard import check_run, apply_run  # noqa

fails = []
def ok(cond, msg):
    if not cond:
        fails.append(msg)

# path tricks
for p in ["AGENTS.md.", "x /a.ts", "a:b.ts", "PROGRA~1/x", "../x", "C:/x", "a//b", "a/./b", "a/<b>"]:
    ok(safe_rel(p) is None, f"safe_rel should reject {p!r}")
ok(safe_rel("apps/web/src/components/A.tsx") == "apps/web/src/components/A.tsx", "normal path")
for p in ["SERVICES/api/src/campus247/main.py", "Apps/Web/src/lib/api.ts", ".ENV", "data/x.json", "apps/web/.env.local"]:
    ok(deny_hit(safe_rel(p) or p, HARD_DENY), f"deny should hit {p}")
ok(not deny_hit("apps/web/src/components/A.tsx", HARD_DENY), "components not denied")

# search/replace
src = "a\n  b\n  c\nd\n"
out, e = apply_edits(src, "<<<<<<< SEARCH\n  b\n=======\n  B\n>>>>>>> REPLACE\n")
ok(out == "a\n  B\n  c\nd\n" and not e, f"exact edit {out!r} {e}")
out, e = apply_edits(src, "<<<<<<< SEARCH\nb\nc\n=======\n  X\n>>>>>>> REPLACE\n")
ok("X" in out and not e, f"fuzzy edit {out!r} {e}")
out, e = apply_edits(src, "<<<<<<< SEARCH\n    2|   b\n=======\n  Y\n>>>>>>> REPLACE\n")
ok("Y" in out and not e, f"line-prefix edit {out!r} {e}")
out, e = apply_edits("x\nx\n", "<<<<<<< SEARCH\nx\n=======\ny\n>>>>>>> REPLACE\n")
ok(e and "matches 2" in e[0], f"ambiguous {e}")
out, e = apply_edits(src, "<<<<<<< SEARCH\nzzz\n=======\ny\n>>>>>>> REPLACE\n")
ok(e and "not found" in e[0], f"not found {e}")

# guard on a fake run against a temp file inside the repo
repo = S.parents[3]
probe = repo / "apps/web/src/components/__nr_offline_probe.tsx"
probe.write_text("export const A = 1;\nexport const B = 2;\nconst k = 'x';\n", encoding="utf-8")
try:
    run = Path(tempfile.mkdtemp())
    (run / "files").mkdir()
    blobs = {
        "red": "export const A = 1;\nexport const B = 2;\nconst k = '<REDACTED>';\n",
        "pref": "    1| export const A = 1;\nexport const B = 2;\n",
        "good": "export const A = 1;\nexport const B = 2;\nconst k = 'y';\n",
    }
    for k, v in blobs.items():
        (run / "files" / f"{k}.txt").write_text(v, encoding="utf-8")
    rel = "apps/web/src/components/__nr_offline_probe.tsx"
    def case(blob, kind, full):
        (run / "meta.json").write_text(json.dumps({"allow": [rel], "mode": "edit", "full_context": full}), encoding="utf-8")
        (run / "files.json").write_text(json.dumps([{"path": rel, "blob": f"files/{blob}.txt", "kind": kind, "edit_errors": []}]), encoding="utf-8")
        (run / "check.json").unlink(missing_ok=True)
        return check_run(run)
    ok(any("REDACTED" in b for b in case("red", "edit", [])["blocking"]), "redacted placeholder blocked")
    ok(any("line-number" in b for b in case("pref", "edit", [])["blocking"]), "line prefix blocked")
    ok(any("did not see in full" in b for b in case("good", "file", [])["blocking"]), "full-context rule")
    ok(not case("good", "file", [rel])["blocking"], "good full file passes")
    r = case("good", "edit", [])
    ok(not r["blocking"], f"good edit passes {r}")
    # stale target refuses apply
    probe.write_text(probe.read_text(encoding="utf-8") + "// user edit\n", encoding="utf-8")
    ok(apply_run(run, []).get("refused", "").startswith("target changed"), "stale refused")
    shutil.rmtree(run)
finally:
    probe.unlink()

print("FAILS:", fails if fails else "none")
sys.exit(1 if fails else 0)
