"""One synthetic service, dedicated SQLite, existing RAG over loopback HTTP."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src"), str(ROOT / "scripts")]
from certificate_stage1_workspace import STATE, checked
from campus247.bootstrap.certificate_demo import create_certificate_demo_app


if __name__ == "__main__":
    import uvicorn
    sys.stdout.reconfigure(encoding="utf-8")
    app = create_certificate_demo_app(checked(STATE / "demo.sqlite3", STATE), frontend_port=3002)
    uvicorn.run(app, host="127.0.0.1", port=8002, access_log=False, log_level="warning")
