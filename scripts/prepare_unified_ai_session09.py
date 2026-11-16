"""Fresh exclusive preimages and read-only audit for UNI-011–015."""
import sys
sys.dont_write_bytecode = True
import prepare_unified_ai_session08 as previous
from unified_ai_runtime_probe import ROOT, checked

previous.previous.STATE = checked(ROOT / "infra/local/unified-ai-20261014-09")
previous.previous.SOURCES = list(dict.fromkeys([*previous.previous.SOURCES,
    "services/api/src/campus247/application/conversation/messages.py",
    "services/api/src/campus247/application/conversation/read.py",
    "services/api/src/campus247/infrastructure/repositories/sqlite_conversations.py",
    "services/api/src/campus247/infrastructure/repositories/held_history.py",
    "services/api/src/campus247/bootstrap/assistant_features.py",
    "services/api/src/campus247/presentation/assistant_state.py",
    "services/api/src/campus247/application/assistance/scoped_context.py",
    "services/api/src/campus247/application/assistance/grants.py",
    "apps/web/src/app/layout.tsx", "apps/web/src/app/chat/page.tsx",
    "apps/web/src/app/privacy/page.tsx", "apps/web/src/features/chat/ChatPanel.tsx",
    "apps/web/src/features/chat/history.ts", "apps/web/src/lib/assistant-context.tsx",
    "apps/web/src/lib/assistant-adapter.ts", "apps/web/src/lib/assistant-state-service.ts",
    "apps/web/src/components/student/AssistantConversation.tsx",
    "apps/web/src/components/student/AssistantWorkspace.tsx",
    "apps/web/src/components/staff/StaffShell.tsx",
    "apps/web/src/features/assistance/AssistanceContextPanel.tsx",
    "apps/web/src/features/documents/CertificateWorkspace.tsx",
    "apps/web/src/features/documents/ServiceWorkspace.tsx",
    "apps/web/src/lib/api/client.ts",
]))

if __name__ == "__main__":
    previous.main()
