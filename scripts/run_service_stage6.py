"""Only synthetic business/source operations; proxy the existing writer8003."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts"), str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")]
from service_stage6_workspace import BUSINESS, checked
from campus247.bootstrap.service_demo import create_service_demo_app

if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=BUSINESS)
    parser.add_argument("--port", type=int, choices=[8004, 8005], default=8004)
    parser.add_argument("--frontend", type=int, choices=[3005])
    args = parser.parse_args()
    database = checked(args.database)
    if args.port == 8004 and database != checked(BUSINESS):
        raise ValueError("stage6 product uses retained shared business DB")
    if args.port == 8005 and not database.is_relative_to(ROOT / "infra/local/service-stage6-20261014-01"):
        raise ValueError("restart worker requires stage6 fixture DB")
    sys.stdout.reconfigure(encoding="utf-8")
    app = create_service_demo_app(database, frontend_port=args.frontend)
    print(json.dumps({"pid": os.getpid(), "database": str(database), "owns_paid_ledger": False,
        "proxy": "http://127.0.0.1:8003", "port": args.port}), flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning", access_log=False)
