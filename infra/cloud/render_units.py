"""Render the systemd units for one runtime profile (default: cloud) from infra/profiles/<name>.toml.

  python infra/cloud/render_units.py --profile cloud --root /opt/campus247 --user campus247 --out /etc/systemd/system

The profile stays the single source for worker count, in-flight limit, provider concurrency, gateway port and caps; the
units only carry what the profile says. Nothing secret is written: units read /etc/campus247/campus247.env
(created by install.sh, mode 0640, not part of the repository).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from runtime_profile import Profile, load_profile  # noqa: E402

COMMON = """[Service]
User={user}
Group={user}
WorkingDirectory={root}
EnvironmentFile=/etc/campus247/campus247.env
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths={root}/infra/local {root}/data {root}/.tooling
Restart=on-failure
RestartSec=3
LimitNOFILE=65536
"""


def units(profile: Profile, root: str, user: str, python: str, node: str) -> dict[str, str]:
    common = COMMON.format(user=user, root=root)
    python_cmd = f"{python} -B -u"
    return {
        "campus247-models.service": f"""[Unit]
Description=Campus 24/7 embedding and reranker model server
After=network.target
{common}
# State directory is created by install.sh; the predecessor is the retained models state it continues.
ExecStart={python_cmd} scripts/serve_rag_models.py --state ${{CAMPUS247_MODELS_STATE}} --predecessor ${{CAMPUS247_MODELS_PREDECESSOR}} --accounting-only
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
""",
        "campus247-gateway.service": f"""[Unit]
Description=Campus 24/7 paid-provider gateway sidecar (owns the ledger lease and the daily cap)
After=network.target
{common}
ExecStart={python_cmd} scripts/gateway_sidecar.py serve --port {profile.gateway_port} --concurrency {profile.provider_concurrency} --daily-usd-cap {profile.daily_usd_cap} --daily-call-cap {profile.daily_call_cap}
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
""",
        "campus247-api.service": f"""[Unit]
Description=Campus 24/7 API ({profile.api_workers} workers)
After=network.target postgresql@17-campus247.service campus247-models.service campus247-gateway.service
Requires=campus247-gateway.service
Wants=campus247-models.service
{common}
Environment=CAMPUS247_RAG_ENGINE=v2
# The learning-materials module scans uploads with a Windows ClamAV build that is not ported to Linux yet.
Environment=CAMPUS_LEARNING_ENABLED=false
Environment=CAMPUS247_RAG_V2_INDEX={root}/data/rag_v2_index/embedded2
Environment=CAMPUS247_CHAT_MAX_IN_FLIGHT={profile.max_in_flight_per_worker}
Environment=CAMPUS247_RATE_LIMIT_STORE=postgres
Environment=CAMPUS247_GATEWAY_URL=http://127.0.0.1:{profile.gateway_port}
Environment=CAMPUS247_GATEWAY_TOKEN_FILE={root}/infra/local/public-rag-20261013/gateway-sidecar.token
ExecStart={python_cmd} scripts/knowledge_platform.py serve --generation --port 8015 --frontend-port 3015{f' --workers {profile.api_workers}' if profile.api_workers > 1 else ''}
TimeoutStartSec=300
# The workers are children of this process; stop them all together.
KillMode=control-group

[Install]
WantedBy=multi-user.target
""",
        "campus247-frontend.service": f"""[Unit]
Description=Campus 24/7 web frontend (internal, behind the HTTPS proxy)
After=network.target
{common}
Environment=CAMPUS247_NODE={node}
ExecStart={python_cmd} scripts/knowledge_platform_frontend.py serve --name ${{CAMPUS247_FRONTEND_NAME}} --port 3015

[Install]
WantedBy=multi-user.target
""",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", default="cloud")
    parser.add_argument("--root", default="/opt/campus247")
    parser.add_argument("--user", default="campus247")
    parser.add_argument("--python", default="/opt/campus247/.venv/bin/python")
    parser.add_argument("--node", default="/usr/bin/node")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    profile = load_profile(args.profile)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, text in units(profile, args.root, args.user, args.python, args.node).items():
        (out / name).write_text(text, encoding="utf-8")
        print("wrote", out / name)


if __name__ == "__main__":
    main()
