"use client";

import React, { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell } from "../../../components/AppShell";
import { ProcedureRunner } from "../../../features/procedures/ProcedureRunner";
import { MyProcedures } from "../../../features/procedures/MyProcedures";

function Content() {
  const params = useSearchParams();
  const runId = params.get("run") ?? undefined;
  return (
    <>
      <ProcedureRunner runId={runId} procedureId={params.get("procedure") ?? undefined} />
      <MyProcedures currentRunId={runId} />
    </>
  );
}

export default function ProcedurePage() {
  return (
    <AppShell activeNav="services">
      <div className="campus-knowledge space-y-6">
        <header className="campus-page-heading">
          <div data-eyebrow="Làm thủ tục cùng trợ lý">
            <h1>Làm thủ tục</h1>
            <p>Trợ lý giúp bạn điền thông tin và kiểm tra điều kiện. Hồ sơ chỉ được gửi khi bạn bấm “Gửi hồ sơ”.</p>
          </div>
        </header>
        <Suspense fallback={<p role="status">Đang tải…</p>}><Content /></Suspense>
      </div>
    </AppShell>
  );
}
