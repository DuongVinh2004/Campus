"""Archive old small ledger and model-accounting records into one tar.gz per day, so a server does not collect tens of
thousands of tiny files a day (the model server writes 2-3 per inference, the gateway 2 per provider call).

  python infra/cloud/compact_ledgers.py --dir infra/local/public-rag-20261013 --pattern "provider-*.json" --keep-newest 5000
  ... --apply     (without --apply nothing is changed; the plan is printed)

Safety: the newest --keep-newest records stay untouched (a restart reads them); each day's archive is written, read back
and compared with the source files byte for byte before any original is removed; only files matching --pattern are
touched; the archive keeps the exact file names. Run it on the cloud server only, never on the local evidence set.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def plan(directory: Path, pattern: str, keep_newest: int, older_than_days: float, now: float | None = None):
    files = sorted((p for p in directory.glob(pattern) if p.is_file()), key=lambda p: (p.stat().st_mtime, p.name))
    candidates = files[:-keep_newest] if keep_newest else files
    cutoff = (now if now is not None else datetime.now(timezone.utc).timestamp()) - older_than_days * 86400
    days: dict[str, list[Path]] = defaultdict(list)
    for path in candidates:
        mtime = path.stat().st_mtime
        if mtime <= cutoff:
            days[datetime.fromtimestamp(mtime, timezone.utc).strftime("%Y%m%d")].append(path)
    return days


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_day(directory: Path, day: str, paths: list[Path], pattern_name: str) -> Path:
    target = directory / "archive" / f"{pattern_name}-{day}.tar.gz"
    if target.exists():
        raise SystemExit(f"{target} already exists; refusing to overwrite")
    target.parent.mkdir(exist_ok=True)
    with tarfile.open(target, "w:gz") as tar:
        for path in paths:
            tar.add(path, arcname=path.name, recursive=False)
    with tarfile.open(target) as tar:  # read back and compare every file before anything is removed
        members = {m.name: m for m in tar.getmembers()}
        if set(members) != {p.name for p in paths}:
            raise SystemExit("archive does not list exactly the planned files")
        for path in paths:
            if digest(tar.extractfile(members[path.name]).read()) != digest(path.read_bytes()):
                raise SystemExit(f"archive differs from {path.name}")
    target.with_suffix(".json").write_text(json.dumps({"day": day, "files": len(paths)}), encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--pattern", required=True)
    parser.add_argument("--keep-newest", type=int, default=5000)
    parser.add_argument("--older-than-days", type=float, default=2)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    days = plan(args.dir, args.pattern, args.keep_newest, args.older_than_days)
    report = {day: len(paths) for day, paths in sorted(days.items())}
    if not args.apply:
        print(json.dumps({"dry_run": True, "would_archive": report}))
        return
    stem = args.pattern.replace("*", "").replace(".json", "").strip("-_.") or "records"
    for day, paths in sorted(days.items()):
        archive_day(args.dir, day, paths, stem)
        for path in paths:
            path.unlink()
    print(json.dumps({"archived": report}))


if __name__ == "__main__":
    main()
