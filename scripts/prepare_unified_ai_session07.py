"""UNI-006 completion preflight; exclusive backups, no runtime mutation."""
import prepare_unified_ai_session06 as previous
from unified_ai_runtime_probe import ROOT, checked

previous.STATE = checked(ROOT / "infra/local/unified-ai-20261014-07")
previous.SOURCES = list(dict.fromkeys([*previous.SOURCES,
    "services/api/src/campus247/application/conversations/feedback.py",
    "services/api/src/campus247/application/privacy/requests.py",
    "services/api/src/campus247/application/identity/session_service.py",
    "services/api/src/campus247/presentation/feedback.py",
    "services/api/src/campus247/presentation/privacy_requests.py",
    "services/api/src/campus247/presentation/logout.py",
    "services/api/src/campus247/presentation/identity.py",
    "services/api/src/campus247/bootstrap/certificate_demo.py",
    "services/api/src/campus247/infrastructure/repositories/sqlite_agent_runs.py",
    "services/api/src/campus247/infrastructure/repositories/sqlite_conversations.py",
    "services/api/src/campus247/bootstrap/consent_storage.py",
    "services/api/src/campus247/application/assistance/durable_services.py",
    "apps/web/src/features/documents/ServiceWorkspace.tsx",
    "apps/web/src/features/documents/CertificateWorkspace.tsx",
    "apps/web/src/app/privacy/page.tsx",
    "apps/web/src/lib/data/api/service-gateway.ts",
]))

if __name__ == "__main__":
    previous.main()
