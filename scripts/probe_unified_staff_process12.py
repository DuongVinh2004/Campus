"""Two-process business/draft contention on explicitly scoped batch fixtures."""
import argparse
import sys
import time
sys.dont_write_bytecode = True
from unified_ai_runtime_probe import ROOT, checked, retain
from unified_completion_scope import completion_fixture
sys.path[:0] = [str(checked(ROOT / "services/api/src")), str(checked(ROOT / "packages/synthetic/src"))]
from campus247.bootstrap.unified_demo import create_unified_demo_app
from campus247.infrastructure.identity.mock import SyntheticIdentityAdapter
from campus247.application.document_request.certificates import CertificateError
from campus247.application.assistance.state_storage import StorageConflict


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("fixture", "ready", "gate", "output", "owner", "case", "client", "kind", "version"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    fixture = checked(ROOT / args.fixture)
    batch = checked(ROOT / "infra/local/unified-ai-20261015-12")
    if (not fixture.is_relative_to(batch) and not completion_fixture(fixture)) or args.kind not in {"draft", "claim"}:
        raise ValueError("only new batch fixtures")
    paths = {name: checked(fixture / getattr(args, name)) for name in ("ready", "gate", "output")}
    if any(path.parent != fixture for path in paths.values()):
        raise ValueError("exact fixture children required")
    app = create_unified_demo_app(checked(fixture / "business.sqlite3"), state_database=checked(fixture / "state.sqlite3"))
    adapter = SyntheticIdentityAdapter("campus247-demo-secret-key-huce", environment="development", tenant_id="huce-local-public")
    actor = adapter.resolve_token(adapter.mint_token(args.owner))
    retain(paths["ready"], {"ready": True})
    deadline = time.monotonic() + 15
    while not paths["gate"].exists():
        if time.monotonic() > deadline:
            raise TimeoutError("fixture start gate")
        time.sleep(.02)
    try:
        if args.kind == "draft":
            result = app.state.staff_drafts.save(actor, {"kind": "service_request", "id": args.case, "expected_version": int(args.version)},
                "Manual process " + args.client, 0, args.client)
        else:
            result = app.state.service_requests.act(actor, args.case, "claim", int(args.version), "process:" + args.client, "Claim from process")
        retain(paths["output"], {"state": "committed", "saved": result.get("saved", False)})
    except (CertificateError, StorageConflict) as exc:
        retain(paths["output"], {"state": "conflict", "code": getattr(exc, "code", "STATE_CONFLICT")})
