import React, { type ReactNode, type ReactElement } from "react";
import Link from "next/link";
import { AlertTriangle, ShieldAlert, ArrowLeft } from "lucide-react";
import { AppShell, type Role } from "../../components/AppShell";

export interface AdminLayoutProps {
  children?: ReactNode;
  userRole?: Role;
  capabilities?: string[];
  sessionStatus?: "authenticated" | "unauthenticated" | "expired";
}

function AdminLayoutComponent({
  children,
  userRole = "admin",
  capabilities = ["ADMIN_ACCESS"],
  sessionStatus = "authenticated",
}: AdminLayoutProps): ReactElement | null {
  // AC-TASK-WEB-ADMIN-001-03: Session expiry check
  if (sessionStatus === "expired") {
    return (
      <AppShell userRole="admin" activeNav="admin">
        <div
          role="alert"
          className="mx-auto my-6 max-w-2xl rounded-2xl border border-red-200 bg-red-50 p-6 text-red-900 shadow-sm dark:border-red-900/60 dark:bg-red-950/60 dark:text-red-200"
        >
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-600 dark:text-red-400" aria-hidden="true" />
            <div>
              <h3 className="mb-2 text-lg font-bold tracking-tight">
                Phiên làm việc đã hết hạn
              </h3>
              <p className="text-sm leading-relaxed text-red-800 dark:text-red-300">
                Phiên làm việc quản trị đã hết hạn hoặc quyền hạn đã bị thay đổi trên máy chủ. Vui lòng làm mới phiên để tiếp tục truy cập.
              </p>
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  // AC-TASK-WEB-ADMIN-001-01 & AC-TASK-WEB-ADMIN-001-02: Deny-by-default capability boundary
  const hasAdminCapability = userRole === "admin" && capabilities.includes("ADMIN_ACCESS");

  if (!hasAdminCapability) {
    return (
      <AppShell userRole={userRole} activeNav="home">
        <div
          role="alert"
          className="fluent-card mx-auto my-10 max-w-xl border border-[var(--border-color)] bg-[var(--surface-card)] p-8 text-center shadow-sm sm:p-10"
        >
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--accent-sand)] text-amber-700 dark:bg-amber-950/60 dark:text-amber-300">
            <ShieldAlert className="h-6 w-6" aria-hidden="true" />
          </div>
          <h2 className="mb-2 text-xl font-bold tracking-tight text-[var(--text-primary)]">
            Không tìm thấy trang hoặc bạn không có thẩm quyền truy cập
          </h2>
          <p className="mb-6 text-sm leading-relaxed text-[var(--text-secondary)]">
            Tài nguyên bạn đang cố truy cập không tồn tại hoặc yêu cầu đặc quyền Quản trị viên hệ thống được cấp phép bởi máy chủ.
          </p>
          <Link
            href="/"
            className="fluent-btn-primary inline-flex items-center justify-center gap-2 text-sm font-semibold"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            <span>Quay về trang chủ</span>
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell userRole="admin" activeNav="admin">
      {children}
    </AppShell>
  );
}

const AdminLayout = AdminLayoutComponent as React.ComponentType<AdminLayoutProps> &
  ((props: any) => ReactElement | null);

export default AdminLayout;
