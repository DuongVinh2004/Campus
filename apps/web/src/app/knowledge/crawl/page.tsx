"use client";

import React from "react";
import { AppShell } from "../../../components/AppShell";
import { KnowledgeCrawl } from "../../../features/knowledge/KnowledgeCrawl";

export default function KnowledgeCrawlPage() {
  return <AppShell activeNav="crawl"><div className="campus-knowledge space-y-6">
    <header className="campus-page-heading"><div><h1>Nguồn tự động từ trang của trường</h1>
      <p>Khai báo trang công khai của HUCE; hệ thống tự dò, lấy văn bản mới hoặc đã thay đổi và đưa vào hàng chờ duyệt.</p></div></header>
    <KnowledgeCrawl />
  </div></AppShell>;
}
