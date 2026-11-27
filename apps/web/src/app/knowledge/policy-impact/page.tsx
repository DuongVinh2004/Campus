"use client";

import React from "react";
import { AppShell } from "../../../components/AppShell";
import { PolicyImpact } from "../../../features/policy/PolicyImpact";

export default function PolicyImpactPage() {
  return (
    <AppShell activeNav="knowledge">
      <div className="campus-knowledge space-y-6">
        <header className="campus-page-heading">
          <div data-eyebrow="Quản trị tri thức">
            <h1>Tác động khi quy chế đổi</h1>
            <p>So mỗi bản phát hành với bản trước: đoạn nào đổi, đổi số liệu hay thời hạn, luật và ca kiểm nào cần rà lại, và nguồn nào ghi mâu thuẫn nhau.</p>
          </div>
        </header>
        <PolicyImpact />
      </div>
    </AppShell>
  );
}
