"""usage: apply_mixed.py <tsx> <mixed.json>: entries {exact original line: [new line, english, vietnamese]}; keys are taken from the new line's t("key")."""
import json
import re
import sys
from pathlib import Path

WEB = Path(r"C:\Users\Duong Vinh\Vinh\apps\web\src")
target, mapping = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
raw = target.read_bytes().decode("utf-8")
nl = "\r\n" if "\r\n" in raw else "\n"
text = raw.replace("\r\n", "\n")
vi_lines, en_lines = [], []
js = lambda v: json.dumps(v, ensure_ascii=False)  # noqa: E731
for original, (new, en, vi) in mapping.items():
    if text.count(original) != 1:
        print("NOT UNIQUE/FOUND:", original.strip()[:70], text.count(original))
        continue
    text = text.replace(original, new)
    key = re.search(r't\("([^"]+)"', new).group(1)
    vi_lines.append(f"  {js(key)}: {js(vi)},")
    en_lines.append(f"  {js(key)}: {js(en)},")
target.write_bytes(text.replace("\n", nl).encode("utf-8"))
for name, lines in (("vi.ts", vi_lines), ("en.ts", en_lines)):
    p = WEB / "lib/i18n" / name
    s = p.read_bytes().decode("utf-8")
    n = "\r\n" if "\r\n" in s else "\n"
    s = s.replace("\r\n", "\n")
    anchor = '  "lang.switchToEnglish"'
    s = s.replace(anchor, "\n".join(lines) + "\n" + anchor)
    p.write_bytes(s.replace("\n", n).encode("utf-8"))
print("applied", len(vi_lines))
