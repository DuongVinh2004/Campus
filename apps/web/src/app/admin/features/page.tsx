"use client";

import React from "react";
import { AppShell } from "../../../components/AppShell";
import { FeatureFlagsPanel } from "../../../features/admin/FeatureFlagsPanel";

export default function AdminFeaturesPage() {
  return (
    <AppShell activeNav="admin">
      <div className="campus-knowledge space-y-6">
        <header className="campus-page-heading">
          <div data-eyebrow="Quản trị hệ thống">
            <h1>Cờ tính năng</h1>
            <p>Bật hoặc tắt từng tính năng. Tắt chỉ ẩn và chặn lối vào, dữ liệu vẫn được giữ.</p>
          </div>
        </header>
        <FeatureFlagsPanel />
      </div>
    </AppShell>
  );
}
