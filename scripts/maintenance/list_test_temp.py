"""List (and, only on request, delete) the per-run `.pytest-tmp*` directories at the repository root.

Default mode is read-only: it writes a CSV of what exists. `--delete LIST.csv` removes only directories
named in that list that still match the strict pattern, sit directly under the repository root and are not
links. The list must be reviewed by the owner first.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PATTERN = re.compile(r"^\.pytest-tmp[A-Za-z0-9._-]*$")


def _is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction and is_junction())


def _size(path: Path) -> tuple[int, bool]:
    total, readable = 0, True
    def onerror(_error):
        nonlocal readable
        readable = False
    for folder, _dirs, files in os.walk(path, onerror=onerror, followlinks=False):
        for name in files:
            try:
                total += os.lstat(os.path.join(folder, name)).st_size
            except OSError:
                readable = False
    return total, readable


def scan(root: Path) -> list[dict]:
    rows = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if not PATTERN.match(entry.name) or not entry.is_dir() or _is_link(entry):
            continue
        size, readable = _size(entry)
        modified = datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")
        rows.append({"name": entry.name, "bytes": size, "modified": modified, "readable": readable})
    return rows


def write_csv(rows: list[dict], target: Path) -> None:
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["name", "bytes", "modified", "readable"])
        writer.writeheader()
        writer.writerows(rows)


def delete_listed(root: Path, listing: Path) -> tuple[list[str], list[str]]:
    deleted, refused = [], []
    with listing.open(newline="", encoding="utf-8") as stream:
        names = [row["name"] for row in csv.DictReader(stream)]
    for name in names:
        target = root / name
        if not PATTERN.match(name) or "/" in name or "\\" in name or target.parent != root:
            refused.append(name)
            continue
        if not target.exists():
            continue
        if _is_link(target) or not target.is_dir():
            refused.append(name)
            continue
        shutil.rmtree(target, ignore_errors=False)
        deleted.append(name)
    return deleted, refused


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--out", type=Path, default=None, help="CSV to write (default: print a summary only)")
    parser.add_argument("--delete", type=Path, default=None, help="CSV reviewed by the owner; delete the directories it names")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.delete:
        deleted, refused = delete_listed(root, args.delete)
        print(f"deleted={len(deleted)} refused={len(refused)}")
        for name in refused:
            print("refused:", name)
        return 1 if refused else 0
    rows = scan(root)
    if args.out:
        write_csv(rows, args.out)
    total = sum(row["bytes"] for row in rows)
    unreadable = sum(1 for row in rows if not row["readable"])
    print(f"directories={len(rows)} bytes={total} unreadable={unreadable}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
