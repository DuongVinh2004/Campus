# E15 — checks on the real local PostgreSQL (2026-11-19)

Cluster `.tooling/knowledge-postgres-20261023` was started (it had not been shut down cleanly; crash recovery replayed 4 WAL records, 0.03 s).

- `freshness-real-postgres.txt`: `FreshnessService.report()` on the live database through a read-only connection: 114 current-release sources, all OK, 7 with unknown applicability. The SQL works on a real PostgreSQL (before this it was only tested with a fake connection).
- `LAST_BACKUP.json`: a full backup of this runtime (302 s, 566 MB). **One file was not backed up**: an `artifacts/<uuid>` file that Windows Defender blocks (68 bytes, left by the upload test with the EICAR test string). The first attempt aborted on such a file; `backup.py` now leaves unreadable files out, names them in `MANIFEST.json` (`skipped_unreadable`), prints a warning and counts them in `LAST_BACKUP.json` (`skipped_files`).
- `REHEARSAL.json`: restore drill into a new database `campus247_rehearsal_20261119161652`: verify 1.5 s, restore 72.3 s, 63 tables identical to live, SQLite integrity 6.6 s, total 95.6 s; the database and the temporary root were removed. The drill failed at first with an `AssertionError` for a relative `--work-dir` (absolute temp path compared with a relative one); fixed with a regression test.

Not covered: restic (not installed), systemd, and a real cloud machine.
