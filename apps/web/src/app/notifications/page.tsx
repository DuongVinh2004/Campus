"use client";
import { SettingsNavigation } from "@/components/shared/SettingsNavigation";
import { AppShell } from "@/components/AppShell";
import { NotificationCenter } from "@/features/notifications/NotificationCenter";
import { NotificationsInbox } from "@/features/notifications/NotificationsInbox";
import { ReminderPreferences } from "@/features/notifications/ReminderPreferences";
import { OPS_ENABLED } from "@/lib/campus-ops-api";
export default function NotificationsPage() {
  if (OPS_ENABLED) return <AppShell activeNav="notifications"><div className="campus-page space-y-6"><NotificationsInbox /><ReminderPreferences kinds={["exam"]} /></div></AppShell>;
  return <AppShell activeNav="notifications"><div className="campus-settings-page"><header className="campus-page-heading"><div><h1>Trung tâm thông báo</h1><p>Theo dõi cập nhật hồ sơ và thông tin dành cho bạn.</p></div></header><SettingsNavigation active="notifications" /><NotificationCenter /></div></AppShell>; }
