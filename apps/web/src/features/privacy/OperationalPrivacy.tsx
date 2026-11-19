"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { ApiClient } from "@/lib/api/client";
import { Check, FileText, Inbox, MessageSquare, ShieldCheck } from "lucide-react";

type Notice = { version: string; effective_at: string; data_categories: string[]; purposes: string[]; retention_summary: string | Record<string, unknown>; disclaimer?: { statement?: string } };
type Consent = { id: string; purpose: string; decision: string; notice_version: string; recorded_at: string };

const LABELS: Record<string, string> = {
  ACCOUNT_CONTEXT: "Thông tin tài khoản", CONVERSATION_CONTENT: "Nội dung hội thoại", REQUEST_METADATA: "Thông tin yêu cầu (siêu dữ liệu)",
  AUDIT_METADATA: "Nhật ký kiểm tra", SERVICE_DELIVERY: "Cung cấp dịch vụ", SAFETY_HANDOVER: "Chuyển cán bộ khi cần an toàn",
  QUALITY_FEEDBACK: "Cải thiện chất lượng trả lời", SECURITY_AUDIT: "Kiểm tra bảo mật",
  GRANTED: "Đồng ý", ACCEPTED: "Đồng ý", DENIED: "Không đồng ý", DECLINED: "Không đồng ý", WITHDRAWN: "Đã rút lại",
};
const label = (code: string) => LABELS[code] ?? code.toLowerCase().replace(/_/g, " ");
const retentionRows = (value: Notice["retention_summary"]): string[] => {
  if (typeof value === "string") return [value];
  const items = Array.isArray(value) ? value : [value];
  return items.map(item => {
    const row = item as { data_class?: string; configured_rule?: string; retention?: string };
    return row.data_class ? `${label(row.data_class)}${row.retention ? `: ${row.retention}` : ""}${row.configured_rule ? ` (quy tắc ${row.configured_rule})` : ""}` : JSON.stringify(item);
  });
};
export function OperationalPrivacy() {
  const [notice, setNotice] = useState<Notice | null>(null), [consents, setConsents] = useState<Consent[]>([]), [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void Promise.all([new ApiClient().get<Notice>("/v1/privacy/notice"), new ApiClient().get<{ items: Consent[] }>("/v1/privacy/consents")]).then(([value, records]) => {
      if (active) { setNotice(value); setConsents(records.items); }
    }).catch(e => { if (active) setError(e instanceof Error ? e.message : "Chưa đọc được dữ liệu quyền riêng tư"); });
    return () => { active = false; };
  }, []);
  return <AppShell activeNav="privacy"><div className="campus-workflow space-y-5"><header className="campus-page-heading"><div><h1 className="text-2xl font-semibold">Quyền riêng tư & dữ liệu cá nhân</h1><p>Thông báo và các quyết định đã lưu cho tài khoản hiện tại.</p></div></header>
    {error && <p role="alert" className="p-4 rounded-xl border border-[var(--border-color)] text-sm">{error} <Link href="/login" className="underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]">Đăng nhập</Link></p>}
    {!notice && !error && <p role="status" className="text-sm py-4">Đang đọc thông tin…</p>}
    {notice && <section className="campus-panel space-y-5">
      <h2 className="text-lg font-semibold flex flex-wrap items-center gap-2">
        <span>Thông báo đang áp dụng · </span>
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border border-[var(--border-color)] bg-[var(--color-primary-light)] text-[var(--color-primary)]">{notice.version}</span>
      </h2>
      {notice.disclaimer?.statement ? (
        <div className="flex items-start gap-3 p-4 rounded-xl border border-[var(--border-color)] bg-[var(--color-primary-light)] text-[var(--color-primary)]">
          <ShieldCheck className="w-5 h-5 mt-0.5 shrink-0" aria-hidden="true" />
          <p className="text-sm leading-relaxed">{notice.disclaimer.statement}</p>
        </div>
      ) : null}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 rounded-xl border border-[var(--border-color)] bg-[var(--surface-card)] space-y-3">
          <h3 className="text-sm font-semibold">Nhóm dữ liệu được xử lý</h3>
          <ul className="flex flex-wrap gap-2 list-none p-0 m-0">
            {notice.data_categories.map(item => (
              <li key={item} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-[var(--border-color)]">
                <Check className="w-3.5 h-3.5 text-[var(--color-primary)] shrink-0" aria-hidden="true" />
                {label(item)}
              </li>
            ))}
          </ul>
        </div>
        <div className="p-4 rounded-xl border border-[var(--border-color)] bg-[var(--surface-card)] space-y-3">
          <h3 className="text-sm font-semibold">Mục đích</h3>
          <ul className="flex flex-wrap gap-2 list-none p-0 m-0">
            {notice.purposes.map(item => (
              <li key={item} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-[var(--border-color)]">
                <Check className="w-3.5 h-3.5 text-[var(--color-primary)] shrink-0" aria-hidden="true" />
                {label(item)}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="p-4 rounded-xl border border-[var(--border-color)] bg-[var(--surface-card)] space-y-3">
        <h3 className="text-sm font-semibold">Thời gian lưu</h3>
        <ul className="space-y-2 list-none p-0 m-0">
          {retentionRows(notice.retention_summary).map(row => (
            <li key={row} className="flex items-start gap-2.5 text-sm">
              <span className="w-2 h-2 rounded-full bg-[var(--color-primary)] mt-1.5 shrink-0" aria-hidden="true" />
              <span>{row}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>}
    {notice && <section className="campus-panel space-y-4">
      <h2 className="text-lg font-semibold">Quyết định đã lưu của tôi</h2>
      {consents.length ? (
        <ul className="space-y-2.5 list-none p-0 m-0">
          {consents.map(record => (
            <li key={record.id} className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl border border-[var(--border-color)] bg-[var(--surface-card)]">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-medium">{label(record.purpose)}</span>
                <span> · </span>
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border border-[var(--border-color)] bg-[var(--color-primary-light)] text-[var(--color-primary)]">{label(record.decision)}</span>
                <span> · </span>
                <span className="text-xs">{new Date(record.recorded_at).toLocaleString("vi-VN")}</span>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="flex flex-col items-center justify-center text-center py-8 px-4 rounded-xl border border-dashed border-[var(--border-color)] space-y-2">
          <Inbox className="w-8 h-8 opacity-60" aria-hidden="true" />
          <p className="text-sm">Chưa có quyết định được ghi nhận cho tài khoản này.</p>
        </div>
      )}
      <p className="text-xs leading-relaxed">Nháp học vụ được lưu riêng theo tài khoản; lưu nháp không gửi hồ sơ đến trường. Lịch sử và biên nhận đã ghi được giữ để đối chiếu.</p>
    </section>}
    <nav className="flex flex-col sm:flex-row gap-3 pt-2">
      <Link href="/tickets" className="inline-flex items-center justify-center gap-2 min-h-[44px] px-5 py-2.5 rounded-xl border border-[var(--border-color)] bg-[var(--surface-card)] text-sm font-medium hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]">
        <FileText className="w-4 h-4 shrink-0" aria-hidden="true" />
        <span>Hồ sơ của tôi</span>
      </Link>
      <Link href="/chat" className="inline-flex items-center justify-center gap-2 min-h-[44px] px-5 py-2.5 rounded-xl border border-[var(--border-color)] bg-[var(--surface-card)] text-sm font-medium hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]">
        <MessageSquare className="w-4 h-4 shrink-0" aria-hidden="true" />
        <span>Lịch sử hội thoại</span>
      </Link>
    </nav>
  </div></AppShell>;
}
