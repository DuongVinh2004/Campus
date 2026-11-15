# Campus 24/7 on a cloud server: install, first start, backup, restore

Target: one Ubuntu 24.04 LTS VM, 4 vCPU / 8 GB, CPU not burstable. The same code and the same files as the development machine;
only `infra/profiles/cloud.toml` differs (2 API workers, in-flight limit 16 per worker, Postgres 256 MB, **temporary** provider caps).
Nothing here is deployed yet: phase 2 starts only when the owner says so. This kit is written and rehearsed in phase 1
(`docs/04-architecture/ROLLOUT_PLAN_LOCAL_THEN_CLOUD_20261115.md`).

## What runs

| Unit | Listens | Role |
|---|---|---|
| `postgresql@17-campus247` | 127.0.0.1:55437 | knowledge database (pgvector, btree_gist) and the shared rate limiter table |
| `campus247-models` | 127.0.0.1:18081, 18082 | embedding (FP32 bge-m3) and reranker; unchanged model and index |
| `campus247-gateway` | 127.0.0.1:8025 | the only process with the provider key, the paid-ledger lease and the daily cap |
| `campus247-api` | 127.0.0.1:8015 | the API, `--workers 2`, shares the port; one worker runs the background jobs (advisory lock) |
| `campus247-frontend` | 127.0.0.1:3015 | Next.js frontend (internal) |
| `caddy` | **:443** | HTTPS; the only listener reachable from outside besides SSH (22) |

## What to put on the server (the owner decides which data)

The code needs the same relative layout as the repository, because it confines every path to the workspace:

```
/opt/campus247/                      repository (git checkout or rsync of the release subset)
  uv.lock, pyproject.toml, scripts/, services/, packages/, infra/profiles/, infra/cloud/, apps/web/ (built snapshot)
  data/rag_v2_index/embedded2/       the retrieval index (≈563 MB)
  infra/local/rag-fixture/           model and ONNX artifacts incl. onnx-linux-20261115/ (hash-pinned Linux runtime)
  infra/local/knowledge-platform-20261023/   state: identity files, keys, artifacts (restored from a backup)
  infra/local/public-rag-20261013/   paid ledger (restored from a backup; the gateway continues the counters)
```

Real student data and accounts are the owner's decision. Without that decision, move **public knowledge only**: the database dump,
the artifacts and the index, and create fresh synthetic accounts on the server (`scripts/knowledge_platform_student.py`).
Never copy `*-credentials.json`, `bootstrap-password.txt` or `.env` unless the owner explicitly says so.

## Install

```bash
sudo CAMPUS247_ROOT=/opt/campus247 CAMPUS247_DOMAIN=chat.example.edu.vn /opt/campus247/infra/cloud/install.sh
```

Idempotent. It installs packages, the dedicated Postgres cluster on 55437 (role and database created, password written only to
`local-connection.json`, mode 0600), Node.js with a verified checksum, the Python 3.12 environment from `uv.lock`, a 2 GB swap file
(safety net only), the systemd units rendered from the profile, Caddy, logrotate, the daily backup timer and a firewall that allows
only 22 and 443. It starts nothing that calls the paid provider.

## First start (in this order)

1. Restore the data: `sudo campus247-restore --backup /path/to/campus247-backup-<stamp> --force` (stop services first).
   The database dump is restored with `pg_restore`; the checksum of every part is verified before anything is written.
2. Put the provider key in `/opt/campus247/.env` (`DEEPSEEK_API_KEY=...`, mode 0600, owner `campus247`). Only the gateway reads it.
3. Decide the daily cap and edit `[gateway]` in `infra/profiles/cloud.toml` (the shipped 5 USD and 2000 calls a day are placeholders),
   then re-run `render_units.py` (install.sh does it) and `systemctl daemon-reload`.
4. `systemctl start campus247-models` and wait until ports 18081/18082 answer (about a minute), then
   `systemctl start campus247-gateway campus247-api campus247-frontend`.
5. Check: `curl -s http://127.0.0.1:8015/health/ready` shows `"status":"ready"`; `curl -s http://127.0.0.1:8025/health` shows `ok`;
   `journalctl -u campus247-api | grep leader_acquired` shows exactly one leader; open `https://<domain>/chat` and ask one question.
6. Warm up before opening to users: in the 4-CPU simulation the first 100-user burst right after a cold start lost the vector branch on
   about 10 % of retrievals (89 % success), while the same burst on a warm stack reached 99.5 %. After any restart of the models or API,
   ask 5 to 10 different questions (several at once) and wait until `journalctl -u campus247-api | grep rag_v2_vector_stats` reports `failed=0`
   for a full interval before announcing that the service is open.

## Backup and restore

`campus247-backup` runs daily at about 03:10 (systemd timer) and keeps the 14 newest folders in `/var/backups/campus247`. Each holds the
database dump, every SQLite store through the SQLite backup API (consistent while the API writes), the state files and the part of the
paid ledger that decides the restart snapshot, with a SHA-256 manifest. **Copy backups off the server** (another host or object storage):
a backup on the same disk does not survive losing the VM. Backups contain secrets (identity files, signing keys): protect them like the server.

Restore rehearsal (do it before going live and after any layout change): `infra/cloud/backup.py verify --backup <dir>`, then restore into
an empty root and start the stack. `restore` refuses to overwrite existing files or a non-empty database unless `--force`.

## Ledgers and logs

The gateway writes two small files per provider call and the model server two or three per inference (about 36,000 files in a heavy day).
`infra/cloud/compact_ledgers.py` archives old records into one tar.gz per day, verified byte for byte before an original is removed
(dry run by default; never run it on the local evidence set). Service logs rotate weekly (`logrotate.conf`).

## Safety notes

- API, gateway, models and Postgres bind to loopback only; the firewall allows 22 and 443.
- The API holds no provider key; the gateway holds it and enforces the cap; the cap is checked before every call.
- `ENVIRONMENT=development` in the env file keeps the demo guards the code expects; changing it is the owner's decision and requires
  setting real secrets for the settings that refuse insecure defaults.
- Updating: stop the API, deploy the new tree, `systemctl start`; the supervisor restarts a dead worker, another worker takes over the background jobs.
