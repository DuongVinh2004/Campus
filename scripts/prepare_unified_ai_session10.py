"""Exclusive preimages/consistent read-only snapshots for UNI-016–020."""
import sys
sys.dont_write_bytecode = True
import prepare_unified_ai_session09 as previous
from unified_ai_runtime_probe import ROOT, checked

previous.previous.previous.STATE = checked(ROOT / "infra/local/unified-ai-20261015-10")
previous.previous.previous.SOURCES = list(dict.fromkeys([
    *previous.previous.previous.SOURCES,
    "services/api/src/campus247/agent/multi_rag.py",
    "services/api/src/campus247/application/multi_agent/contracts.py",
    "services/api/src/campus247/application/multi_agent/orchestrator.py",
    "services/api/src/campus247/application/multi_agent/service_adapter.py",
    "services/api/src/campus247/application/single_agent/controller.py",
    "services/api/src/campus247/application/single_agent/resources.py",
    "services/api/src/campus247/agent/tools/registry.py",
    "services/api/src/campus247/agent/tools/executor.py",
    "services/api/src/campus247/application/assistance/grant_consumers.py",
    "services/api/src/campus247/infrastructure/repositories/sqlite_agent_runs.py",
    "services/api/src/campus247/bootstrap/app.py",
    "services/api/src/campus247/presentation/agent_runs.py",
    "apps/web/src/lib/unified-assistant-runtime.tsx",
    "apps/web/src/lib/unified-ai-contracts.ts",
    "apps/web/src/features/assistance/UnifiedAssistantWorkspace.tsx",
]))

if __name__ == "__main__":
    previous.previous.main()
