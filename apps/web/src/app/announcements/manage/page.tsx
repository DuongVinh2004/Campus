"use client";

import React from "react";
import { AppShell } from "../../../components/AppShell";
import { AnnouncementCompose } from "../../../features/announcements/AnnouncementCompose";
import { AnnouncementManager } from "../../../features/announcements/AnnouncementManager";

export default function ManageAnnouncementsPage() {
  return (
    <AppShell activeNav="announcements">
      <div className="campus-knowledge space-y-6">
        <header className="campus-page-heading">
          <div data-eyebrow="Soạn và gửi">
            <h1>Soạn thông báo</h1>
            <p>Chọn đối tượng, xem số người nhận, rồi xác nhận gửi. Thông báo đã gửi có thể thu hồi.</p>
          </div>
        </header>
        <AnnouncementCompose />
        <AnnouncementManager />
      </div>
    </AppShell>
  );
}
