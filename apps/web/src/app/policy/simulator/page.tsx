"use client";

import React from "react";
import { AppShell } from "../../../components/AppShell";
import { PolicySimulator } from "../../../features/policy/PolicySimulator";

export default function PolicySimulatorPage() {
  return (
    <AppShell activeNav="policySimulator">
      <div className="campus-knowledge space-y-6">
        <header className="campus-page-heading">
          <div data-eyebrow="Quy chế đào tạo">
            <h1>Kiểm tra điều kiện theo quy chế</h1>
            <p>Nhập số liệu của bạn để biết có đạt điều kiện hay không, kèm điều khoản làm căn cứ và ngưỡng cần đạt.</p>
          </div>
        </header>
        <PolicySimulator />
      </div>
    </AppShell>
  );
}
