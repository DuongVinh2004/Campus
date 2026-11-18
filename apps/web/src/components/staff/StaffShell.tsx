"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Inbox, FileSearch, ChevronLeft } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Navbar } from "@/components/Navbar";
import { useStore } from "@/lib/store";
import { DataAccessState } from "@/components/shared/DataAccessState";
import { LoadingState } from "@/components/shared/LoadingState";
import { UnifiedAssistantWorkspace } from "@/features/assistance/UnifiedAssistantWorkspace";
import { AccessibleDialog } from "@/components/shared/AccessibleDialog";

export const staffButton = "fluent-btn-secondary text-sm";
export const staffPrimary = "fluent-btn-primary text-sm font-semibold";
export const staffField = "fluent-input text-sm";
export const staffSurface = "fluent-card";

export function StaffShell({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  const { currentUser, isDataLoading } = useStore();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(wide);
  const [assistantOpen, setAssistantOpen] = useState(false);
  if (isDataLoading) return <><Navbar /><LoadingState title="Đang tải bàn làm việc…" description="Đang đọc dữ liệu hồ sơ." /></>;
  if (currentUser?.role !== "officer") return <DataAccessState requiredRole="officer" />;
  return <div className="staff-workspace min-h-dvh bg-[var(--bg-page)] text-[var(--text-primary)]">
    <a href="#staff-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-xl focus:bg-white focus:p-3 focus:text-slate-900 dark:focus:bg-slate-900 dark:focus:text-slate-100 dark:focus:border dark:focus:border-slate-700">Đến nội dung chính</a>
    <Navbar />
    <div className="mx-auto flex max-w-[1920px] gap-5 px-4 py-3 xl:px-6">
      <aside className={`${collapsed ? "w-14" : "w-48"} hidden shrink-0 lg:block`} aria-label="Bàn làm việc cán bộ">
        <div className="sticky top-20 space-y-2">
          <button type="button" onClick={() => setCollapsed(!collapsed)} className={`${staffButton} w-full`} aria-label={collapsed ? "Mở rộng điều hướng" : "Thu gọn điều hướng"} aria-expanded={!collapsed}><ChevronLeft className={`h-4 w-4 ${collapsed ? "rotate-180" : ""}`} />{!collapsed && "Bàn làm việc"}</button>
          {[{ href: "/dashboard", label: "Hồ sơ dịch vụ", icon: Inbox, active: pathname.startsWith("/dashboard") || pathname.startsWith("/tickets") }, { href: "/reviews", label: "Rà soát học phần", icon: FileSearch, active: pathname.startsWith("/reviews") }].map(item => <Link key={item.href} href={item.href} aria-current={item.active ? "page" : undefined} aria-label={item.label} title={collapsed ? item.label : undefined} className={`flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium ${item.active ? "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300" : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"}`}><item.icon className="h-5 w-5 shrink-0" aria-hidden="true" />{!collapsed && item.label}</Link>)}
          {!collapsed && <p className="px-3 pt-5 text-xs leading-relaxed text-slate-500">{currentUser.department || "Bàn tiếp nhận và xử lý hồ sơ"}</p>}
        </div>
      </aside>
      <main id="staff-content" className="min-w-0 flex-1">{process.env.NEXT_PUBLIC_UNIFIED_AI === "true" && <button type="button" onClick={() => setAssistantOpen(true)} className={staffButton}>Trợ lý và quyền cán bộ</button>}{children}</main>
    </div>
    {process.env.NEXT_PUBLIC_UNIFIED_AI === "true" && <AccessibleDialog open={assistantOpen} onClose={() => setAssistantOpen(false)} labelledBy="staff-assistant-title" className="fixed inset-3 flex min-h-0 flex-col bg-white dark:bg-slate-950 lg:left-auto lg:w-[620px]"><header className="flex justify-between p-3"><h2 id="staff-assistant-title">Trợ lý cán bộ</h2><button type="button" className={staffButton} onClick={() => setAssistantOpen(false)}>Đóng</button></header><UnifiedAssistantWorkspace compact /></AccessibleDialog>}
  </div>;
}
