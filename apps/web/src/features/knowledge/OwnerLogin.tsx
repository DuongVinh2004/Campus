"use client";
import React, { useEffect, useState } from "react";
import { announceSessionChange } from "../learning/learning-session";

export function OwnerLogin() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  useEffect(() => setReady(true), []);
  return (
    <main className="campus-login">
      <div className="campus-login-card fluent-card border border-[var(--border-color)] bg-[var(--surface-card)] p-6 shadow-xs space-y-4">
        <div className="campus-login-brand"><span className="campus-login-mark" aria-hidden="true">C</span><span>Campus 24/7<small>Đại học Xây dựng Hà Nội</small></span></div>
        <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">Đăng nhập Campus 24/7</h1>
        <p className="text-xs leading-relaxed text-[var(--text-secondary)]">Tài khoản quản trị hoặc sinh viên local do chủ hệ thống cấp. Chưa kết nối SSO HUCE; tài khoản sinh viên local không có dữ liệu điểm hoặc lịch học HUCE.</p>
        <form method="post" className="space-y-4" onSubmit={async event => {
          event.preventDefault(); setBusy(true); setError("");
          const data = new FormData(event.currentTarget);
          try {
            const response = await fetch("/v1/knowledge/platform/session", { method: "POST", credentials: "include",
              headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: data.get("username"), password: data.get("password") }) });
            if (!response.ok) throw new Error(response.status === 401 || response.status === 403
              ? "Tài khoản hoặc mật khẩu không hợp lệ."
              : response.status === 429 ? "Đăng nhập tạm thời bị giới hạn. Vui lòng thử lại sau."
              : "Dịch vụ đăng nhập chưa sẵn sàng. Vui lòng thử lại sau.");
            const result = await response.json();
          announceSessionChange();
            const redirect = new URLSearchParams(window.location.search).get("redirect") || "";
            const internal = redirect.startsWith("/") && !redirect.startsWith("//") && !/[\\\u0000-\u0020\u007f]/.test(redirect);
            window.location.assign(internal ? redirect : result.roles?.includes("SUPPORT_OFFICER") ? "/staff" : result.roles?.some((role: string) => ["LECTURER", "SYSTEM_ADMIN"].includes(role)) ? "/learning" : result.roles?.includes("STUDENT") ? "/chat" : result.roles?.includes("KNOWLEDGE_CONTRIBUTOR") ? "/knowledge/documents" : "/knowledge/sources");
          } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
        }}>
          <label className="block text-xs font-semibold text-[var(--text-secondary)]">Tài khoản<input className="fluent-input mt-1 w-full text-sm" name="username" autoComplete="username" required maxLength={100} /></label>
          <label className="block text-xs font-semibold text-[var(--text-secondary)]">Mật khẩu
            <span className="campus-login-password">
              <input className="fluent-input mt-1 w-full text-sm" type={showPassword ? "text" : "password"} name="password" autoComplete="current-password" required maxLength={200} />
              <button type="button" className="campus-login-reveal" aria-pressed={showPassword} onClick={() => setShowPassword(value => !value)}>{showPassword ? "Ẩn" : "Hiện"}<span className="sr-only"> mật khẩu</span></button>
            </span>
          </label>
          <button className="fluent-btn-primary w-full text-sm font-semibold shadow-xs" disabled={!ready || busy}>{busy ? "Đang đăng nhập…" : "Đăng nhập"}</button>
          {error && <p role="alert" className="rounded-xl border border-[var(--color-danger-subtle)] bg-[var(--surface-subtle)] p-3 text-xs text-[var(--color-danger)]">{error}</p>}
        </form>
        <div className="pt-2 text-center">
          <a href="/chat" className="text-xs text-[var(--color-primary)] hover:underline">Mở chatbot và xem trạng thái kho</a>
        </div>
      </div>
    </main>
  );
}
