import type { ReactNode } from "react";
import "./globals.css";
import { StoreProvider } from "@/lib/store";
import { DraftSessionProvider } from "@/lib/draft-context";
import { DataSourceError } from "@/components/shared/DataSourceError";
import { UnifiedAssistantProvider } from "@/lib/unified-assistant-runtime";
import { KnowledgeAvailability } from "@/features/knowledge/KnowledgeAvailability";
import { ChatDraftSessionProvider } from "@/features/chat/route-drafts";
import { KnowledgeWorkspaceSession } from "@/features/knowledge/KnowledgeWorkspaceSession";
import { PwaRegister } from "@/components/PwaRegister";
import { ThemeProvider } from "@/lib/theme";
import { LanguageProvider } from "@/lib/i18n";

export const metadata = {
  title: "Campus 24/7 — Cổng Dịch Vụ Số & Trợ Lý Học Vụ HUCE",
  description:
    "Cổng dịch vụ một cửa số và Trợ lý học vụ AI hỗ trợ tra cứu quy chế đào tạo, thủ tục hành chính — Trường Đại học Xây dựng Hà Nội (HUCE)",
  keywords: ["campus", "HUCE", "AI", "trợ lý", "một cửa", "thời khóa biểu"],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="vi" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var stored = localStorage.getItem('campus247_theme_v2');
                  var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
                  if (stored === 'dark' || (!stored && prefersDark)) {
                    document.documentElement.classList.add('dark');
                  } else {
                    document.documentElement.classList.remove('dark');
                  }
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body className="min-h-screen flex flex-col font-sans antialiased selection:bg-blue-600 selection:text-white transition-colors" style={{ backgroundColor: "var(--bg-page)", color: "var(--text-primary)" }}>
        <LanguageProvider>
        <ThemeProvider>
        {process.env.NEXT_PUBLIC_KNOWLEDGE_PLATFORM === "true" ? <ChatDraftSessionProvider><div className="knowledge-operational"><KnowledgeAvailability /><div className="knowledge-operational-content"><KnowledgeWorkspaceSession>{children}</KnowledgeWorkspaceSession></div></div></ChatDraftSessionProvider> : <StoreProvider>
          <DraftSessionProvider>
            <DataSourceError />
            <div className="flex-1 flex flex-col min-h-0">
              {process.env.NEXT_PUBLIC_UNIFIED_AI === "true" ? <UnifiedAssistantProvider>{children}</UnifiedAssistantProvider> : children}
            </div>
          </DraftSessionProvider>
        </StoreProvider>}
        </ThemeProvider>
        </LanguageProvider>
        <PwaRegister />
      </body>
    </html>
  );
}
