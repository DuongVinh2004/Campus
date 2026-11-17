"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { ApiClient } from "@/lib/api/client";

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
    {error && <p role="alert">{error} <Link href="/login" className="underline">Đăng nhập</Link></p>}
    {!notice && !error && <p role="status">Đang đọc thông tin…</p>}
    {notice && <section className="campus-panel space-y-3"><h2 className="text-lg font-semibold">Thông báo đang áp dụng · {notice.version}</h2><p>{notice.disclaimer?.statement}</p><h3 className="font-medium">Nhóm dữ liệu được xử lý</h3><ul className="list-disc pl-5">{notice.data_categories.map(item => <li key={item}>{label(item)}</li>)}</ul><h3 className="font-medium">Mục đích</h3><ul className="list-disc pl-5">{notice.purposes.map(item => <li key={item}>{label(item)}</li>)}</ul><h3 className="font-medium">Thời gian lưu</h3><ul className="list-disc pl-5">{retentionRows(notice.retention_summary).map(row => <li key={row}>{row}</li>)}</ul></section>}
    {notice && <section className="campus-panel space-y-3"><h2 className="text-lg font-semibold">Quyết định đã lưu của tôi</h2>{consents.length ? <ul>{consents.map(record => <li key={record.id}>{label(record.purpose)} · {label(record.decision)} · {new Date(record.recorded_at).toLocaleString("vi-VN")}</li>)}</ul> : <p>Chưa có quyết định được ghi nhận cho tài khoản này.</p>}<p>Nháp học vụ được lưu riêng theo tài khoản; lưu nháp không gửi hồ sơ đến trường. Lịch sử và biên nhận đã ghi được giữ để đối chiếu.</p></section>}
    <nav className="flex gap-4"><Link href="/tickets" className="underline">Hồ sơ của tôi</Link><Link href="/chat" className="underline">Lịch sử hội thoại</Link></nav>
  </div></AppShell>;
}
