"""Runtime profiles: strict loading, memory check before any start, and the launcher's refusals."""
import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import runtime_profile as rp  # noqa: E402

spec = importlib.util.spec_from_file_location("knowledge_platform_runtime", ROOT / "scripts/knowledge_platform_runtime.py")
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)

GOOD = """name = "t"
[api]
workers = 1
max_in_flight_per_worker = 4
provider_concurrency = 5
[postgres]
shared_buffers = "64MB"
max_connections = 10
[gateway]
port = 8025
daily_usd_cap = "2.50"
daily_call_cap = 100
[memory]
reserve_mb = 100
postgres_mb = 10
frontend_mb = 20
api_worker_mb = 30
worker_mb = 40
gateway_mb = 7
"""


def write(tmp_path, text, name="t"):
    (tmp_path / f"{name}.toml").write_text(text, encoding="utf-8")
    return tmp_path


def test_local_profile_keeps_the_values_the_launcher_used_before_profiles():
    local = rp.load_profile("local")
    assert (local.pg_shared_buffers, local.pg_max_connections) == ("128MB", 20)
    assert local.api_workers == 2  # raised from 1 by rollout step 1.8


def test_local_gateway_is_uncapped_as_today_and_cloud_is_never_uncapped():
    local, cloud = rp.load_profile("local"), rp.load_profile("cloud")
    assert (local.daily_usd_cap, local.daily_call_cap, local.provider_concurrency) == ("0", 0, 16)
    assert float(cloud.daily_usd_cap) > 0 and cloud.daily_call_cap > 0


def test_cloud_profile_matches_the_design_table():
    cloud = rp.load_profile("cloud")
    assert (cloud.api_workers, cloud.max_in_flight_per_worker, cloud.provider_concurrency) == (2, 16, 24)
    assert (cloud.pg_shared_buffers, cloud.pg_max_connections) == ("256MB", 40)


def test_good_profile_loads(tmp_path):
    profile = rp.load_profile("t", write(tmp_path, GOOD))
    assert profile.required_mb(["api", "postgres"]) == 100 + 30 * 1 + 10
    assert profile.required_mb(["gateway"]) == 107
    assert (profile.gateway_port, profile.daily_usd_cap, profile.daily_call_cap) == (8025, "2.50", 100)


@pytest.mark.parametrize("mutation", [
    lambda t: t.replace("workers = 1\n", ""),                              # missing key
    lambda t: t.replace("[memory]", "extra = 1\n[memory]"),                # unknown key lands in [postgres]
    lambda t: t.replace("workers = 1", 'workers = "1"'),                   # wrong type
    lambda t: t.replace("workers = 1", "workers = true"),                  # bool is not an int
    lambda t: t.replace("workers = 1", "workers = 0"),                     # below minimum
    lambda t: t.replace("reserve_mb = 100", "reserve_mb = -1"),            # negative
    lambda t: t.replace('name = "t"', 'name = "other"'),                   # name differs from file
    lambda t: t + "\n[surprise]\nx = 1\n",                                 # unknown section
    lambda t: "not toml [",
    lambda t: t.replace('daily_usd_cap = "2.50"', 'daily_usd_cap = "-1"'),         # negative cap
    lambda t: t.replace('daily_usd_cap = "2.50"', 'daily_usd_cap = "lots"'),       # not a decimal
    lambda t: t.replace('daily_usd_cap = "2.50"', "daily_usd_cap = 2.5"),          # must be a string, never a float
    lambda t: t.replace("port = 8025", "port = 80"),                               # privileged port
])
def test_loader_is_strict(tmp_path, mutation):
    with pytest.raises(rp.ProfileError):
        rp.load_profile("t", write(tmp_path, mutation(GOOD)))


@pytest.mark.parametrize("name", ["", "../local", "a/b", "local.toml", "nope"])
def test_profile_name_cannot_escape_the_profile_directory(name):
    with pytest.raises(rp.ProfileError):
        rp.load_profile(name)


def test_memory_check_refuses_when_components_do_not_fit(tmp_path):
    profile = rp.load_profile("t", write(tmp_path, GOOD))
    assert rp.check_memory(profile, ["api"], available_mb=130) == 130
    with pytest.raises(rp.ProfileError, match="nothing was started"):
        rp.check_memory(profile, ["api"], available_mb=129)


def test_memory_check_is_skipped_when_everything_is_reused(tmp_path):
    profile = rp.load_profile("t", write(tmp_path, GOOD))
    assert rp.check_memory(profile, [], available_mb=0) == 0


def test_unknown_component_is_rejected(tmp_path):
    profile = rp.load_profile("t", write(tmp_path, GOOD))
    with pytest.raises(ValueError):
        profile.required_mb(["queue"])


def test_available_memory_reads_the_os():
    assert rp.available_memory_mb() > 0


@pytest.mark.skipif(os.name != "nt", reason="the launcher runs the Windows runtime; on Linux systemd starts the units")
def test_launcher_refuses_a_profile_with_more_workers_than_it_supports(monkeypatch):
    from dataclasses import replace
    too_many = replace(rp.load_profile("local"), api_workers=runtime.MAX_API_WORKERS + 1)
    monkeypatch.setattr(runtime, "load_profile", lambda name: too_many)
    with pytest.raises(RuntimeError, match="supports 1 to"):
        runtime.start(profile="local")


class _Anything:
    def is_file(self):
        return True

    def is_dir(self):
        return True

    def __truediv__(self, other):
        return self

    def __str__(self):
        return "stub"


@pytest.mark.skipif(os.name != "nt", reason="the launcher runs the Windows runtime; on Linux systemd starts the units")
def test_launcher_refuses_before_starting_anything_when_memory_is_short(monkeypatch):
    stub = _Anything()
    monkeypatch.setattr(runtime, "checked_path", lambda path, root: stub)
    monkeypatch.setattr(runtime, "select_frontend", lambda name: "build")
    monkeypatch.setattr(runtime, "frontend_path", lambda name: stub)
    monkeypatch.setattr(runtime, "connection", lambda: None)
    monkeypatch.setattr(runtime, "model_identity", lambda: None)
    monkeypatch.setattr(runtime, "process_inventory", lambda frontend: [])
    monkeypatch.setattr(runtime, "listening", lambda port: False)
    monkeypatch.setattr(rp, "available_memory_mb", lambda: 100)
    monkeypatch.setattr(runtime, "check_memory", lambda profile, comps: rp.check_memory(profile, comps, 100))
    launched = []
    monkeypatch.setattr(runtime.subprocess, "run", lambda *a, **k: launched.append(a))
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *a, **k: launched.append(a))
    with pytest.raises(RuntimeError, match="not enough free memory"):
        runtime.start(profile="local")
    assert launched == []


@pytest.mark.skipif(os.name != "nt", reason="the launcher runs the Windows runtime; on Linux systemd starts the units")
def test_launcher_skips_the_memory_check_when_every_component_is_running(monkeypatch):
    stub = _Anything()
    seen = []
    monkeypatch.setattr(runtime, "checked_path", lambda path, root: stub)
    monkeypatch.setattr(runtime, "select_frontend", lambda name: "build")
    monkeypatch.setattr(runtime, "frontend_path", lambda name: stub)
    monkeypatch.setattr(runtime, "connection", lambda: None)
    monkeypatch.setattr(runtime, "model_identity", lambda: None)
    monkeypatch.setattr(runtime, "process_inventory", lambda frontend: [])
    monkeypatch.setattr(runtime, "listening", lambda port: True)
    monkeypatch.setattr(runtime, "matching_processes", lambda rows, kind, frontend: [1])
    monkeypatch.setattr(runtime, "check_memory", lambda profile, comps: seen.append(list(comps)) or 0)
    # Stop right after the check: the scope directory step is the first thing that touches the disk.
    monkeypatch.setattr(runtime, "datetime", type("D", (), {"now": staticmethod(lambda tz=None: (_ for _ in ()).throw(KeyError("stop")))}))
    with pytest.raises(KeyError):
        runtime.start(profile="local")
    assert seen == [[]]
