"use client";
import React, { useState } from "react";

export function OwnerLogin() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return <main className="mx-auto max-w-lg space-y-5 p-8"><h1 className="text-2xl font-semibold">Đăng nhập Campus 24/7</h1>
    <p>Tài khoản quản trị hoặc sinh viên local do chủ hệ thống cấp. Chưa kết nối SSO HUCE; tài khoản sinh viên local không có dữ liệu điểm hoặc lịch học HUCE.</p>
    <form className="space-y-4" onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError("");
      const data = new FormData(event.currentTarget);
      try {
        const response = await fetch("/v1/knowledge/platform/session", { method: "POST", credentials: "include",
          headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: data.get("username"), password: data.get("password") }) });
        if (!response.ok) throw new Error("Tài khoản hoặc mật khẩu không hợp lệ, hoặc phiên đăng nhập tạm thời bị giới hạn.");
        const result = await response.json();
        const redirect = new URLSearchParams(window.location.search).get("redirect") || "";
        const internal = redirect.startsWith("/") && !redirect.startsWith("//") && !/[\\\u0000-\u0020\u007f]/.test(redirect);
        window.location.assign(internal ? redirect : result.roles?.includes("STUDENT") ? "/chat" : "/knowledge/sources");
      } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
    }}><label className="block">Tài khoản<input className="fluent-input w-full" name="username" autoComplete="username" required maxLength={100} /></label>
      <label className="block">Mật khẩu<input className="fluent-input w-full" type="password" name="password" autoComplete="current-password" required maxLength={200} /></label>
      <button className="fluent-btn-primary" disabled={busy}>{busy ? "Đang đăng nhập…" : "Đăng nhập"}</button>
      {error && <p role="alert">{error}</p>}
    </form><a href="/chat" className="underline">Mở chatbot và xem trạng thái kho</a></main>;
}
