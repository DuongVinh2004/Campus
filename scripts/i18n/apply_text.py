"""Replace Vietnamese text by t("<prefix>.N") when the text is a quoted string, an attribute value or plain JSX text.

Usage: python apply_text.py FILE MAPPING.json PREFIX [--start N]
MAPPING.json is {"Vietnamese": "English", ...}. Every occurrence in the file is replaced.
Keys are appended to lib/i18n/vi.ts and en.ts. Text that fills only part of a longer
string (for example an interpolated template literal) is reported and left alone.
"""
import json
import re
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "apps" / "web" / "src"


def read(p):
    s = p.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in s else "\n"
    return s.replace("\r\n", "\n"), nl


def write(p, s, nl):
    p.write_bytes(s.replace("\n", nl).encode("utf-8"))


def main():
    file = Path(sys.argv[1])
    mapping = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    prefix = sys.argv[3]
    n = int(sys.argv[sys.argv.index("--start") + 1]) if "--start" in sys.argv else 1
    text, nl = read(file)
    vi_lines, en_lines, missed = [], [], []
    for vi, en in mapping.items():
        key = f"{prefix}.{n}"
        call = f't("{key}")'
        quoted = f'"{vi}"'
        done = 0
        for q in (quoted, f"'{vi}'"):
            if q in text:
                text = re.sub(r'=' + re.escape(q), "={" + call + "}", text)
                text = text.replace(q, call)
                done = 1
        if vi in text:
            # plain JSX text: only when the surrounding characters are markup
            pat = re.compile(r"(?<=[>\s])" + re.escape(vi) + r"(?=\s*<|\s*$|\s*\{)", re.M)
            if pat.search(text):
                text = pat.sub("{" + call + "}", text)
                done = 1
        if not done:
            missed.append(vi)
            continue
        vi_lines.append(f'  {json.dumps(key)}: {json.dumps(vi, ensure_ascii=False)},')
        en_lines.append(f'  {json.dumps(key)}: {json.dumps(en, ensure_ascii=False)},')
        n += 1
    write(file, text, nl)
    for name, lines in (("vi.ts", vi_lines), ("en.ts", en_lines)):
        p = WEB / "lib" / "i18n" / name
        s, k = read(p)
        s = s.replace('  "lang.switchToEnglish"', "\n".join(lines) + '\n  "lang.switchToEnglish"', 1)
        write(p, s, k)
    print("applied", len(vi_lines), "next index", n)
    for m in missed:
        print("MISSED:", m)


main()
