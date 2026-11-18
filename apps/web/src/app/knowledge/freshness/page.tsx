"use client";

import React from "react";
import { AppShell } from "../../../components/AppShell";
import { FreshnessPanel } from "../../../features/knowledge/FreshnessPanel";

export default function KnowledgeFreshnessPage() {
  return (
    <AppShell activeNav="knowledge">
      <div className="campus-knowledge space-y-6">
        <header className="campus-page-heading">
          <div data-eyebrow="Quản trị tri thức">
            <h1>Nguồn sắp hết hạn và cần rà soát</h1>
            <p>Theo dõi hiệu lực của từng nguồn để chatbot không dùng tài liệu đã lỗi thời.</p>
          </div>
        </header>
        <FreshnessPanel />
      </div>
    </AppShell>
  );
}
