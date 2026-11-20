"""Apply a vi->en mapping to a TSX file: replace the literals by t("prefix.N") and add the keys to vi.ts / en.ts.
usage: i18n_apply.py <tsx file> <mapping.json> <prefix>"""
import json
import re
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "apps/web/src"
target, mapping_path, prefix = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
raw = target.read_bytes().decode("utf-8")
nl = "\r\n" if "\r\n" in raw else "\n"
text = raw.replace("\r\n", "\n")
vi_lines, en_lines = [], []


def js(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


for index, (vi, en) in enumerate(mapping.items(), 1):
    key = f"{prefix}.{index}"
    before = text
    # JSX text node
    text = re.sub(r">(\s*)" + re.escape(vi) + r"(\s*)<", lambda m: f">{m.group(1)}{{t(\"{key}\")}}{m.group(2)}<", text)
    # JSX text that fills a whole line
    text = re.sub(r"(?m)^(\s*)" + re.escape(vi) + r"$", lambda m: f"{m.group(1)}{{t(\"{key}\")}}", text)
    # attribute string: name="vi"  -> name={t("k")}
    text = re.sub(r'(=)"' + re.escape(vi) + '"', lambda m: f'={{t("{key}")}}', text)
    # any other plain string literal
    text = text.replace('"' + vi + '"', f't("{key}")')
    if text == before:
        print("NOT FOUND:", vi[:70])
        continue
    vi_lines.append(f"  {js(key)}: {js(vi)},")
    en_lines.append(f"  {js(key)}: {js(en)},")
target.write_bytes(text.replace("\n", nl).encode("utf-8"))
for name, lines in (("vi.ts", vi_lines), ("en.ts", en_lines)):
    p = WEB / "lib/i18n" / name
    s = p.read_bytes().decode("utf-8")
    n = "\r\n" if "\r\n" in s else "\n"
    s = s.replace("\r\n", "\n")
    anchor = '  "lang.switchToEnglish"'
    assert s.count(anchor) == 1
    s = s.replace(anchor, "\n".join(lines) + "\n" + anchor)
    p.write_bytes(s.replace("\n", n).encode("utf-8"))
print("applied", len(vi_lines), "of", len(mapping))
