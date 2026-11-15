"""Runtime profiles: the only place where the local machine and the cloud VM differ.

A profile is a TOML file in infra/profiles. The loader is strict (missing or unknown keys fail) so a typo cannot
silently fall back to a default. The memory check compares the estimated memory of the components about to be
started with the memory the operating system reports as available. It never kills or changes anything.
"""
from __future__ import annotations

import ctypes
import os
import tomllib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

PROFILE_DIR = Path(__file__).resolve().parents[1] / "infra" / "profiles"
COMPONENTS = ("postgres", "frontend", "gateway", "api", "worker")

_SCHEMA = {
    "api": {"workers": int, "max_in_flight_per_worker": int, "provider_concurrency": int},
    "postgres": {"shared_buffers": str, "max_connections": int},
    "gateway": {"port": int, "daily_usd_cap": str, "daily_call_cap": int},
    "memory": {"reserve_mb": int, "postgres_mb": int, "frontend_mb": int, "api_worker_mb": int, "worker_mb": int,
               "gateway_mb": int},
}


class ProfileError(RuntimeError):
    pass


@dataclass(frozen=True)
class Profile:
    name: str
    api_workers: int
    max_in_flight_per_worker: int
    provider_concurrency: int
    pg_shared_buffers: str
    pg_max_connections: int
    reserve_mb: int
    postgres_mb: int
    frontend_mb: int
    api_worker_mb: int
    worker_mb: int
    gateway_mb: int
    gateway_port: int
    daily_usd_cap: str
    daily_call_cap: int

    def required_mb(self, components) -> int:
        """Estimated MB needed to start `components` now, including the safety reserve."""
        unknown = set(components) - set(COMPONENTS)
        if unknown:
            raise ValueError(f"unknown component: {sorted(unknown)}")
        sizes = {"postgres": self.postgres_mb, "frontend": self.frontend_mb, "gateway": self.gateway_mb,
                 "api": self.api_worker_mb * self.api_workers, "worker": self.worker_mb}
        return self.reserve_mb + sum(sizes[item] for item in set(components))


def load_profile(name: str, directory: Path = PROFILE_DIR) -> Profile:
    if not name or not name.replace("-", "").replace("_", "").isalnum():
        raise ProfileError("profile name must be a plain identifier")
    path = directory / f"{name}.toml"
    if not path.is_file():
        raise ProfileError(f"profile '{name}' not found")
    try:
        with open(path, "rb") as handle:  # builtin open: independent of how Path.open is wrapped by callers
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise ProfileError(f"profile '{name}' is not valid TOML: {error}") from None
    if set(data) != {"name", *_SCHEMA}:
        raise ProfileError(f"profile '{name}' must contain exactly: name, " + ", ".join(_SCHEMA))
    if data["name"] != name:
        raise ProfileError(f"profile file '{name}.toml' declares name '{data['name']}'")
    for section, keys in _SCHEMA.items():
        table = data[section]
        if not isinstance(table, dict) or set(table) != set(keys):
            raise ProfileError(f"[{section}] must contain exactly: " + ", ".join(keys))
        for key, kind in keys.items():
            value = table[key]
            if type(value) is not kind or (kind is int and value < 0) or (kind is str and not value):
                raise ProfileError(f"[{section}] {key} must be a {'non-negative integer' if kind is int else 'non-empty string'}")
    api, pg, mem = data["api"], data["postgres"], data["memory"]
    if api["workers"] < 1 or api["max_in_flight_per_worker"] < 1 or api["provider_concurrency"] < 1:
        raise ProfileError("[api] values must be at least 1")
    if pg["max_connections"] < 1:
        raise ProfileError("[postgres] max_connections must be at least 1")
    gw = data["gateway"]
    if not 1024 <= gw["port"] <= 65535:
        raise ProfileError("[gateway] port must be 1024-65535")
    try:
        if Decimal(gw["daily_usd_cap"]) < 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        raise ProfileError("[gateway] daily_usd_cap must be a non-negative decimal string (0 = no cap)") from None
    return Profile(name, api["workers"], api["max_in_flight_per_worker"], api["provider_concurrency"],
                   pg["shared_buffers"], pg["max_connections"], mem["reserve_mb"], mem["postgres_mb"],
                   mem["frontend_mb"], mem["api_worker_mb"], mem["worker_mb"], mem["gateway_mb"],
                   gw["port"], gw["daily_usd_cap"], gw["daily_call_cap"])


def available_memory_mb() -> int:
    """Memory the OS says can be allocated without swapping (Windows and Linux; no third-party package)."""
    if os.name == "nt":
        class Status(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total_phys", ctypes.c_ulonglong),
                        ("avail_phys", ctypes.c_ulonglong), ("total_page", ctypes.c_ulonglong),
                        ("avail_page", ctypes.c_ulonglong), ("total_virtual", ctypes.c_ulonglong),
                        ("avail_virtual", ctypes.c_ulonglong), ("avail_extended", ctypes.c_ulonglong)]
        status = Status()
        status.length = ctypes.sizeof(Status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise ProfileError("cannot read available memory")
        return int(status.avail_phys // (1024 * 1024))
    for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    raise ProfileError("cannot read available memory")


def check_memory(profile: Profile, components, available_mb: int | None = None) -> int:
    """Refuse (ProfileError) when the components to start do not fit; return the estimate when they do."""
    if not set(components):
        return 0  # everything is already running and is reused: nothing new to fit
    needed = profile.required_mb(components)
    available = available_memory_mb() if available_mb is None else available_mb
    if available < needed:
        raise ProfileError(f"not enough free memory for profile '{profile.name}': starting {', '.join(sorted(set(components)))} "
                           f"needs about {needed} MB, {available} MB available; nothing was started")
    return needed
