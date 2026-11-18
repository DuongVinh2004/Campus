"use client";
import Link from "next/link";
import { Building2, CalendarDays, LifeBuoy, Search, Sparkles } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { UnifiedAssistantWorkspace } from "./UnifiedAssistantWorkspace";

export function UnavailableStudentSurface({ kind }: { kind: "rooms" | "schedule" }) {
  const isRooms = kind === "rooms";

  return (
    <AppShell activeNav={kind}>
      <main className="campus-page min-w-0 space-y-6">
        <header className="campus-page-heading">
          <div>
            <h1 className="text-2xl font-semibold">
              {isRooms ? "Phòng học" : "Lịch học cá nhân"}
            </h1>
            <p role="status">
              {isRooms
                ? "Chưa có kết nối đặt phòng trong bản hợp nhất. Chưa có phòng được đặt hoặc hủy từ trang này."
                : "Chưa có nguồn lịch học cá nhân được kết nối trong bản hợp nhất."}
            </p>
          </div>
        </header>

        <section className="campus-panel flex flex-col items-center p-6 text-center sm:p-10">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[var(--color-primary-light)] text-[var(--color-primary)]">
            {isRooms ? (
              <Building2 className="h-7 w-7" aria-hidden="true" />
            ) : (
              <CalendarDays className="h-7 w-7" aria-hidden="true" />
            )}
          </div>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            {isRooms ? "Chưa kết nối phân hệ phòng học" : "Chưa kết nối nguồn lịch học cá nhân"}
          </h2>
          <p className="mt-2 max-w-lg text-sm leading-relaxed text-[var(--text-secondary)]">
            {isRooms
              ? "Hệ thống hiện chưa thiết lập đầu nối trực tiếp tới dữ liệu phòng học. Không có dữ liệu phòng trống hoặc đặt phòng thực tế trong giao diện này."
              : "Hệ thống hiện chưa thiết lập đầu nối trực tiếp tới thời khóa biểu cá nhân. Không có dữ liệu lịch học tự động trong giao diện này."}
          </p>

          <nav className="mt-6 flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:items-center">
            <Link
              href="/chat"
              className="inline-flex min-h-[44px] w-full sm:w-auto items-center justify-center gap-2 rounded-lg bg-[var(--color-primary)] px-5 py-2.5 text-sm font-medium text-[var(--color-on-primary)] transition-colors hover:bg-[var(--color-primary-hover)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
            >
              <Search className="h-4 w-4 shrink-0" aria-hidden="true" />
              Tra cứu nguồn công khai
            </Link>
            <Link
              href="/services?kind=GENERAL_SUPPORT"
              className="inline-flex min-h-[44px] w-full sm:w-auto items-center justify-center gap-2 rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] px-5 py-2.5 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
            >
              <LifeBuoy className="h-4 w-4 shrink-0" aria-hidden="true" />
              Chuẩn bị yêu cầu hỗ trợ
            </Link>
          </nav>
        </section>

        {process.env.NEXT_PUBLIC_KNOWLEDGE_PLATFORM === "true" ? (
          <section className="campus-panel">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--color-primary-light)] text-[var(--color-primary)]">
                <Sparkles className="h-4 w-4" aria-hidden="true" />
              </div>
              <div>
                <h2 className="font-semibold text-[var(--text-primary)]">
                  Tra cứu và chuẩn bị tại cùng một nơi
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">
                  Hỏi trợ lý về quy chế, hoặc mở dịch vụ học vụ để lưu nháp yêu cầu bằng tài khoản hiện tại.
                </p>
              </div>
            </div>
          </section>
        ) : (
          <section className="h-[65dvh] min-h-80 overflow-hidden rounded-xl border border-[var(--border-color)] bg-[var(--surface-card)]">
            <UnifiedAssistantWorkspace compact />
          </section>
        )}
      </main>
    </AppShell>
  );
}
