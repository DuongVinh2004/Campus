"use client";

import React from "react";
import { AppShell } from "../../../components/AppShell";
import { AnswerQualityPanel } from "../../../features/knowledge/AnswerQualityPanel";
import { VerificationPanel } from "../../../features/knowledge/VerificationPanel";
import { StudentGapReports } from "../../../features/knowledge/StudentGapReports";

export default function KnowledgeQualityPage() {
  return (
    <AppShell activeNav="knowledge">
      <div className="campus-knowledge space-y-6">
        <header className="campus-page-heading">
          <div data-eyebrow="Quản trị tri thức">
            <h1>Chất lượng câu trả lời</h1>
            <p>Những chỗ chatbot hay từ chối hoặc bị đánh giá chưa hữu ích, để biết nên bổ sung hay rà soát nguồn nào.</p>
          </div>
        </header>
        <AnswerQualityPanel />
        <VerificationPanel />
        <StudentGapReports />
      </div>
    </AppShell>
  );
}
