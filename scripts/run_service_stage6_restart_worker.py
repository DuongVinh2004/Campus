"""Fresh owned test worker with graceful lifecycle; never targets API8003/8004."""
import hmac
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts"), str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src")]
from service_stage6_workspace import destination
from campus247.bootstrap.service_demo import create_service_demo_app

if __name__ == "__main__":
    import uvicorn
    from fastapi import Request, HTTPException
    from starlette.background import BackgroundTask
    from starlette.responses import JSONResponse
    nonce = os.environ.get("CAMPUS247_STAGE6_LIFECYCLE_NONCE")
    if not nonce or len(nonce) < 32:
        raise ValueError("owned test lifecycle binding required")
    app = create_service_demo_app(destination("process-restart.sqlite3"))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8005, access_log=False, log_level="warning"))
    def allowed(request):
        if not hmac.compare_digest(request.headers.get("X-Test-Lifecycle", ""), nonce):
            raise HTTPException(403)
    @app.get("/internal/owned-test/status")
    def status(request: Request):
        allowed(request)
        return {"pid": os.getpid(), "fixture_database": str(destination("process-restart.sqlite3")), "owns_paid_ledger": False}
    @app.post("/internal/owned-test/exit")
    def exit_owned(request: Request):
        allowed(request)
        def shutdown():
            server.should_exit = True
        return JSONResponse({"graceful_exit": True}, background=BackgroundTask(shutdown))
    server.run()
