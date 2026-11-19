"use client";

import React from "react";
import { AppShell } from "../../../components/AppShell";
import { KnowledgeDocuments } from "../../../features/knowledge/KnowledgeDocuments";

export default function KnowledgeDocumentsPage() {
  return <AppShell activeNav="documents"><div className="campus-knowledge space-y-6">
    <header className="campus-page-heading"><div><h1>Thêm tài liệu cho trợ lý học vụ</h1>
      <p>Tải một tài liệu lên; hệ thống tự kiểm tra, phát hành và cập nhật chatbot. Chỉ cần một lần duyệt nếu tài khoản của bạn cần người duyệt.</p></div></header>
    <KnowledgeDocuments />
  </div></AppShell>;
}
