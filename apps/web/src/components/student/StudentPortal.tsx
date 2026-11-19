"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { Navbar } from "@/components/Navbar";
import { DataAccessState } from "@/components/shared/DataAccessState";
import { LoadingState } from "@/components/shared/LoadingState";
import { useStore } from "@/lib/store";
import { useStudentWorkspace } from "@/lib/student-workspace";

function PortalContents({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { storageIssue } = useStudentWorkspace();
  const isChat = pathname === "/student/assistant";
  return <div className="min-h-dvh bg-[var(--bg-page)] bg-[radial-gradient(ellipse_at_top_left,rgba(59,130,246,0.08),transparent_60%)] text-[var(--text-primary)]">
    <a href="#student-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-xl focus:bg-white focus:px-4 focus:py-3 focus:text-slate-900 dark:focus:bg-slate-900 dark:focus:text-slate-100 dark:focus:border dark:focus:border-slate-700">Đến nội dung chính</a>
    <Navbar />
    <main id="student-content" className={isChat ? "w-full" : "mx-auto w-full max-w-[1120px] px-4 pb-20 pt-5 sm:px-6 sm:pt-6 lg:px-8"}>
      {storageIssue && <p role="alert" className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">{storageIssue}</p>}
      {children}
    </main>
  </div>;
}

export function StudentPortal({ children }: { children: ReactNode }) {
  const { currentUser, isDataLoading } = useStore();
  if (isDataLoading) return <div className="min-h-dvh"><Navbar /><LoadingState title="Đang tải dịch vụ sinh viên…" /></div>;
  if (!currentUser || currentUser.role !== "student") return <DataAccessState requiredRole="student" />;
  return <PortalContents>{children}</PortalContents>;
}
