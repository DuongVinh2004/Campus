"use client";

import React from "react";
import { AppShell } from "../../../components/AppShell";
import { FeatureGate } from "../../../lib/features";
import { PolicyRulesAdmin } from "../../../features/policy/PolicyRulesAdmin";

export default function PolicyRulesPage() {
  return (
    <AppShell activeNav="knowledge">
      <div className="campus-knowledge space-y-6">
        <header className="campus-page-heading">
          <div data-eyebrow="Quản trị tri thức">
            <h1>Luật từ quy chế</h1>
            <p>Mỗi luật trích nguyên văn quy chế đã phát hành. Bản nháp phải qua kiểm tự động và người duyệt trước khi công bố.</p>
          </div>
        </header>
        <FeatureGate feature="policy.rules"><PolicyRulesAdmin /></FeatureGate>
      </div>
    </AppShell>
  );
}
