"""Dedicated process-restart test server; fixed fresh test database and port."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src"), str(ROOT / "scripts")]
from certificate_stage1_workspace import STATE, checked
from campus247.bootstrap.certificate_demo import create_certificate_demo_app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_certificate_demo_app(checked(STATE / "process-restart.sqlite3", STATE)),
                host="127.0.0.1", port=8003, access_log=False, log_level="warning")
