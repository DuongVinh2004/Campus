"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Lock,
  Mail,
  Eye,
  EyeOff,
  LogIn,
  AlertCircle,
  HelpCircle,
  X,
  ChevronDown,
} from "lucide-react";
import { AuthLayout } from "@/components/AuthLayout";
import { useStore } from "@/lib/store";
import { AccessibleDialog } from "@/components/shared/AccessibleDialog";
import { CERTIFICATE_DEMO } from "@/lib/data/api/certificate-gateway";
import { CertificateLogin } from "@/features/documents/CertificateWorkspace";
import { OwnerLogin } from "@/features/knowledge/OwnerLogin";
import { UniversitySignIn } from "@/features/auth/UniversitySignIn";

function LoginForm() {
  const router = useRouter();

  const { login } = useStore();

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [helpDialogOpen, setHelpDialogOpen] = useState(false);
  const closeHelpDialog = React.useCallback(() => setHelpDialogOpen(false), []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmed = identifier.trim().toLowerCase();
    if (!trimmed) {
      setError("Vui lòng nhập tài khoản.");
      return;
    }
    if (!password) {
      setError("Vui lòng nhập mật khẩu.");
      return;
    }

    setLoading(true);

    try {
      // Find matching user
      let matchedUserId = "";
      if (trimmed.includes("an.nv") || trimmed === "sv001" || trimmed === "20210018") {
        matchedUserId = "SV001";
      } else if (trimmed.includes("ha.tt") || trimmed === "of001") {
        matchedUserId = "OF001";
      } else if (trimmed.includes("tram.lb") || trimmed === "sv024" || trimmed === "20240019") {
        matchedUserId = "SV024";
      } else {
        setLoading(false);
        setError("Không tìm thấy tài khoản. Vui lòng kiểm tra lại email trường hoặc mã số được cấp.");
        return;
      }

      if (password !== "demo1234") {
        setLoading(false);
        setError("Tài khoản hoặc mật khẩu không chính xác.");
        return;
      }

      const success = await login(matchedUserId, rememberMe);
      setLoading(false);

      if (success) {
        if (matchedUserId === "OF001") {
          router.push("/staff");
        } else {
          router.push("/");
        }
      } else {
        setError("Tài khoản hoặc mật khẩu không chính xác.");
      }
    } catch {
      setLoading(false);
      setError("Có lỗi xảy ra, vui lòng thử lại.");
    }
  };

  return (
    <div className="space-y-5">
      <div className="space-y-1.5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-primary)]">
          Đăng nhập hệ thống
        </p>
        <h2 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">
          Đăng nhập tài khoản
        </h2>
      </div>

      {error && (
        <div id="login-error" role="alert" aria-live="assertive" className="p-3 rounded-xl bg-[var(--surface-subtle)] border border-[var(--color-danger-subtle)] flex items-start gap-2 text-xs text-[var(--color-danger)]">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="identifier" className="mb-1 block text-xs font-semibold text-[var(--text-secondary)]">
            Tài khoản
          </label>
          <div className="relative">
            <Mail className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-3.5" />
            <input
              id="identifier"
              name="identifier"
              type="text"
              autoComplete="username"
              aria-invalid={error ? "true" : "false"}
              aria-describedby={error ? "login-error" : undefined}
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="Email hoặc mã tài khoản (VD: sv001)"
              className="fluent-input pl-9 pr-3 text-sm"
            />
          </div>
        </div>

        <div>
          <label htmlFor="password" className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
            Mật khẩu
          </label>
          <div className="relative">
            <Lock className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-3.5" />
            <input
              id="password"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              aria-invalid={error ? "true" : "false"}
              aria-describedby={error ? "login-error" : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="fluent-input pl-9 pr-10 text-sm"
            />
            <button
              type="button"
              aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-3 text-[var(--text-secondary)] hover:text-[var(--text-primary)] cursor-pointer min-h-[36px] min-w-[36px] flex items-center justify-center"
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <div className="text-xs">
          <label className="flex items-center gap-2 cursor-pointer text-[var(--text-secondary)]">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="h-4 w-4 rounded border-[var(--border-color)] accent-[var(--color-primary)] text-[var(--color-primary)] focus:ring-[var(--color-primary)]"
            />
            <span>Ghi nhớ tài khoản</span>
          </label>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="fluent-btn-primary w-full text-sm font-semibold shadow-xs"
        >
          {loading ? (
            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <>
              <LogIn className="w-4 h-4" />
              <span>Đăng nhập</span>
            </>
          )}
        </button>
      </form>

      {/* Shown only when the server offers sign-in with the school account */}
      <UniversitySignIn />

      {/* Quick Demo Switcher */}
      <details className="campus-auth-demo"><summary>Chọn tài khoản mô phỏng</summary>
        <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] mb-2">
          Chọn tài khoản:
        </p>
        <div className="flex flex-col gap-1.5">
          {[
            { id: "sv001", role: "Sinh viên", name: "Nguyễn Văn An (K66)" },
            { id: "of001", role: "Cán bộ Một cửa", name: "Trần Thị Hà (Phòng CTSV)" },
            { id: "sv024", role: "Sinh viên năm 1", name: "Lê Bảo Trâm (K69)" },
          ].map((acc) => (
            <button
              key={acc.id}
              type="button"
              onClick={() => {
                setIdentifier(acc.id);
                setPassword("demo1234");
                setError(null);
              }}
              className="flex items-center justify-between px-3 py-2 rounded-lg bg-[var(--surface-subtle)] hover:bg-[var(--color-primary-light)] border border-[var(--border-color)] text-left transition-colors cursor-pointer group"
            >
              <div className="min-w-0">
                <div className="text-xs font-semibold text-[var(--text-primary)] group-hover:text-[var(--color-primary)]">
                  {acc.name}
                </div>
                <div className="text-[11px] text-[var(--text-secondary)]">
                  {acc.role} • Mã: <span className="font-mono font-medium">{acc.id}</span>
                </div>
              </div>
              <span className="text-[11px] font-semibold text-[var(--color-primary)] opacity-0 group-hover:opacity-100 transition-opacity">
                Chọn →
              </span>
            </button>
          ))}
        </div>
      </details>

      <div className="fluent-card border border-[var(--border-color)] bg-[var(--surface-subtle)] p-3 text-xs text-[var(--text-secondary)]">
        <p className="font-semibold text-[var(--text-primary)]">Hướng dẫn đăng nhập:</p>
        <p className="mt-1 text-[11px] leading-relaxed">
          Đăng nhập bằng tài khoản Cổng đào tạo hoặc email trường (@huce.edu.vn) để truy cập các dịch vụ Một cửa số và Trợ lý AI.
        </p>
      </div>

      <div className="pt-1 text-center">
        <button
          type="button"
          onClick={() => setHelpDialogOpen(true)}
          className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--color-primary)] transition-colors"
        >
          <HelpCircle className="w-3.5 h-3.5" />
          <span>Cần trợ giúp đăng nhập?</span>
        </button>
      </div>

      {/* Help Dialog Modal */}
      {helpDialogOpen && (
        <AccessibleDialog
          open={helpDialogOpen}
          onClose={closeHelpDialog}
          labelledBy="help-dialog-title"
          className="w-full max-w-md"
        >
          <div
            className="w-full max-w-md rounded-2xl bg-[var(--surface-card)] border border-[var(--border-color)] p-6 shadow-2xl space-y-4 text-[var(--text-primary)]"
          >
            <div className="flex items-center justify-between">
              <div id="help-dialog-title" className="flex items-center gap-2 font-bold text-sm text-[var(--text-primary)]">
                <HelpCircle className="w-4 h-4 text-[var(--color-primary)]" />
                <span>Trợ giúp đăng nhập</span>
              </div>
              <button
                type="button"
                onClick={closeHelpDialog}
                aria-label="Đóng trợ giúp đăng nhập"
                className="p-1 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-sm leading-relaxed text-[var(--text-secondary)]">
              <p>Hãy sử dụng email trường hoặc mã số được cấp để đăng nhập.</p>
              <p>Nếu thông tin đăng nhập không hoạt động, hãy liên hệ Phòng CTSV hoặc quản trị viên Campus 24/7.</p>
            </div>

            <div className="pt-2 text-right">
              <button
                type="button"
                onClick={closeHelpDialog}
                className="fluent-btn-secondary text-xs font-semibold"
              >
                Đã hiểu
              </button>
            </div>
          </div>
        </AccessibleDialog>
      )}
    </div>
  );
}

export default function LoginPage() {
  if (process.env.NEXT_PUBLIC_KNOWLEDGE_PLATFORM === "true") return <OwnerLogin />;
  if (CERTIFICATE_DEMO) return <CertificateLogin />;
  return (
    <AuthLayout>
      <LoginForm />
    </AuthLayout>
  );
}
