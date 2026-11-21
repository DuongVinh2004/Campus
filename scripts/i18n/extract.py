import json, re, sys
from pathlib import Path
VI = re.compile(r"[à-ỹĐđÀ-Ỹ]")
res = {"literals": [], "lines": [], "mixed": []}
for f in sys.argv[1:]:
    text = Path(f).read_text(encoding="utf-8")
    lits = {}
    for m in re.finditer(r">([^<>{}\n]*)<", text):
        s = m.group(1).strip()
        if s and VI.search(s): lits.setdefault(s, "jsx")
    for m in re.finditer(r'"((?:[^"\\n]|\.)*)"', text):
        s = m.group(1)
        if VI.search(s) and not s.startswith(("@/", "./", "../")): lits.setdefault(s, "str")
    for s in lits: res["literals"].append([f, s])
    for line in text.splitlines():
        if not VI.search(line): continue
        st = line.strip()
        if st in lits: continue
        if re.fullmatch(r"[^<>{}=;`\"]+", st): res["lines"].append([f, st])
        elif st.startswith("//") or st.startswith("*") or st.startswith("/*"): continue
        else:
            if not any(l == st for l in lits): res["mixed"].append([f, line.rstrip()])
print(json.dumps(res, ensure_ascii=False, indent=0))
