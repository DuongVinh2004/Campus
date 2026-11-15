# Runtime profiles

`local.toml` (this Windows machine) and `cloud.toml` (Linux VM, 4 vCPU / 8 GB) are the only place the two
environments differ. Loaded by `scripts/runtime_profile.py`; selected with `--profile` on the launcher:

```bash
infra/local/rag-fixture/.venv/Scripts/python.exe -B scripts/knowledge_platform_runtime.py start --profile local ...
```

- The loader is strict: every key is required and unknown keys fail, so a typo cannot fall back to a default.
- Before starting anything the launcher estimates the memory of the components it would start (already running
  components are reused and not counted) and refuses if the OS reports less available memory. Nothing is started
  or stopped when it refuses.
- Used now: `[postgres]` options, `[memory]`, and `[api] workers` (the launcher refuses a value it cannot honour;
  `cloud.toml` asks for 2 and is refused until step 1.8).
- Declared, consumed in later steps: `max_in_flight_per_worker` (1.2) and `provider_concurrency` (1.7).
- Memory figures are estimates; re-measure them on the real VM (rollout step 2.3).
