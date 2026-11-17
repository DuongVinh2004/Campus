"""Print the profile's runtime settings as KEY=VALUE lines for shells that do not use systemd (the Docker simulation).

  eval "$(python infra/cloud/profile_env.py --profile cloud)"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from runtime_profile import load_profile  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="cloud")
    args = parser.parse_args()
    p = load_profile(args.profile)
    for key, value in (("API_WORKERS", p.api_workers), ("MAX_IN_FLIGHT", p.max_in_flight_per_worker),
                       ("PROVIDER_CONCURRENCY", p.provider_concurrency), ("GATEWAY_PORT", p.gateway_port),
                       ("DAILY_USD_CAP", p.daily_usd_cap), ("DAILY_CALL_CAP", p.daily_call_cap)):
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
