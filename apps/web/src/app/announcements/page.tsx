"use client";

import React, { useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { AnnouncementInbox } from "../../features/announcements/AnnouncementInbox";

export default function AnnouncementsPage() {
  const [id, setId] = useState<string | null | undefined>(undefined);
  useEffect(() => { setId(new URLSearchParams(window.location.search).get("id")); }, []);
  return (
    <AppShell activeNav="announcements">
      <div className="campus-knowledge space-y-6">
        <header className="campus-page-heading">
          <div data-eyebrow="Nhà trường">
            <h1>Thông báo</h1>
            <p>Thông báo chính thức gửi đến bạn. Thông báo khẩn chưa đọc luôn nằm đầu danh sách.</p>
          </div>
        </header>
        {id !== undefined && <AnnouncementInbox initialId={id} />}
      </div>
    </AppShell>
  );
}
