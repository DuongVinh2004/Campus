"""Exclusive preimages and consistent read-only retained DB snapshots for U4."""
import sys
sys.dont_write_bytecode = True
import prepare_unified_ai_session10 as prior
from unified_ai_runtime_probe import ROOT, checked

base = prior.previous.previous.previous
base.STATE = checked(ROOT / "infra/local/unified-ai-20261015-11")
base.SOURCES = list(dict.fromkeys([*base.SOURCES,
    "services/api/src/campus247/application/document_request/assistant.py",
    "services/api/src/campus247/application/document_request/certificates.py",
    "services/api/src/campus247/application/document_request/service_requests.py",
    "services/api/src/campus247/domain/document_request/certificate.py",
    "services/api/src/campus247/domain/service_request.py",
    "apps/web/src/lib/data/api/certificate-gateway.ts",
    "apps/web/src/lib/data/api/service-gateway.ts",
    "apps/web/src/components/student/VinUniForm.tsx",
    "apps/web/src/lib/api/client.ts",
]))

if __name__ == "__main__":
    prior.previous.previous.main()
