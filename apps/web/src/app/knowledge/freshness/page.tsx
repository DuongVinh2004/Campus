"use client";

import React from "react";
import { AppShell } from "../../../components/AppShell";
import { FreshnessPanel } from "../../../features/knowledge/FreshnessPanel";

export default function KnowledgeFreshnessPage() {
  return (
    <AppShell activeNav="knowledge">
      <div className="campus-knowledge space-y-6">
        <FreshnessPanel />
      </div>
    </AppShell>
  );
}
