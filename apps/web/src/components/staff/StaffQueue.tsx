"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RefreshCw, Search } from "lucide-react";
import { useStore } from "@/lib/store";
import { filterTickets, ticketTypeLabels } from "@/lib/staff-policy";
import { formatDate } from "@/lib/format-date";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { StaffShell, staffButton, staffField, staffSurface } from "./StaffShell";
import { queuePosition, rememberQueuePosition } from "./queue-navigation";

export function StaffQueue() {
  const { tickets, reloadData, currentUser } = useStore();
  const [filters, setFilters] = useState({ q: "", status: "active", priority: "all", type: "all", page: 1 });
  const [hydrated, setHydrated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [updated, setUpdated] = useState("");
  useEffect(() => {
    const read = () => { const p = new URLSearchParams(window.location.search); setFilters({ q: p.get("q") || "", status: ["all", "active", "open", "pending_officer", "resolved"].includes(p.get("status") || "") ? p.get("status")! : "active", priority: p.get("priority") === "high" ? "high" : "all", type: Object.keys(ticketTypeLabels).includes(p.get("type") || "") ? p.get("type")! : "all", page: Math.max(1, Number(p.get("page")) || 1) }); setHydrated(true); };
    read(); window.addEventListener("popstate", read); return () => window.removeEventListener("popstate", read);
  }, []);
  function change(next: Partial<typeof filters>) {
    const value = { ...filters, ...next, page: next.page ?? 1 }; setFilters(value);
    const p = new URLSearchParams(); Object.entries(value).forEach(([key, val]) => p.set(key, String(val)));
    const url = `/dashboard?${p}`;
    if (url !== window.location.pathname + window.location.search) {
      if (Object.keys(next).length === 1 && "q" in next) window.history.replaceState(null, "", url);
      else window.history.pushState(null, "", url);
    }
  }
  const result = filterTickets(tickets, filters.q, filters.status, filters.priority, filters.type);
  const pages = Math.max(1, Math.ceil(result.length / 20));
  const page = Math.min(pages, Math.floor(filters.page));
  const visible = result.slice((page - 1) * 20, page * 20);
  useEffect(() => {
    if (!hydrated || !Number.isFinite(page)) return;
    if (filters.page !== page) {
      const params = new URLSearchParams(window.location.search);
      params.set("page", String(page));
      window.history.replaceState(null, "", `/dashboard?${params}`);
    }
  }, [hydrated, filters.page, page]);
  useEffect(() => {
    if (!hydrated || !currentUser) return;
    const saved = queuePosition(currentUser.id);
    if (!saved || saved.url !== window.location.pathname + window.location.search) return;
    const frame = requestAnimationFrame(() => {
      document.getElementById(saved.focusId)?.focus({ preventScroll: true });
      window.scrollTo({ top: saved.scrollY });
    });
    return () => cancelAnimationFrame(frame);
  }, [hydrated, currentUser]);
  async function refresh() { if (busy) return; setBusy(true); setError(""); try { await reloadData(); setUpdated(new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Bangkok" }).format(new Date())); } catch (e) { setError(e instanceof Error ? e.message : "Chưa làm mới được. Kết quả trước đó được giữ lại."); } finally { setBusy(false); } }
  return <StaffShell>
    <header className="mb-3 flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-semibold tracking-tight">Hàng chờ hồ sơ</h1><p className="sr-only">Tiếp nhận, kiểm tra và phản hồi sinh viên.</p></div><div className="flex items-center gap-3"><span role="status" className="text-xs text-slate-500">{updated && `Đã làm mới ${updated}`}</span><button onClick={() => void refresh()} disabled={busy} className={staffButton}><RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} />{busy ? "Đang làm mới…" : "Làm mới"}</button></div></header>
    <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Phạm vi hàng chờ">
      {[{ label: "Chưa hoàn tất", count: tickets.filter(t => t.status !== "resolved").length, status: "active", priority: "all" }, { label: "Ưu tiên cao", count: tickets.filter(t => t.status !== "resolved" && t.priority === "high").length, status: "active", priority: "high" }, { label: "Đã hoàn tất", count: tickets.filter(t => t.status === "resolved").length, status: "resolved", priority: "all" }].map(item => <button key={item.label} aria-pressed={filters.status === item.status && filters.priority === item.priority} onClick={() => change({ status: item.status, priority: item.priority })} className={`${staffButton} ${filters.status === item.status && filters.priority === item.priority ? "border-blue-500 text-blue-700 dark:text-blue-300" : ""}`}>{item.label}<span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs dark:bg-slate-800">{item.count}</span></button>)}
    </div>
    <section className={staffSurface} aria-label="Danh sách hồ sơ">
      <div className="grid gap-3 border-b border-slate-200 p-3 md:grid-cols-[minmax(220px,1fr)_170px_170px_150px] dark:border-slate-800">
        <label className="relative"><span className="sr-only">Tìm mã hồ sơ, tên, mã sinh viên</span><Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" /><input className={`${staffField} pl-9`} value={filters.q} onChange={e => change({ q: e.target.value })} placeholder="Mã hồ sơ, tên, mã sinh viên…" /></label>
        <select aria-label="Loại yêu cầu" className={staffField} value={filters.type} onChange={e => change({ type: e.target.value })}><option value="all">Mọi loại yêu cầu</option>{Object.entries(ticketTypeLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
        <select aria-label="Trạng thái hồ sơ" className={staffField} value={filters.status} onChange={e => change({ status: e.target.value })}><option value="active">Chưa hoàn tất</option><option value="all">Mọi trạng thái</option><option value="open">Mới tiếp nhận</option><option value="pending_officer">Chờ xử lý</option><option value="resolved">Hoàn tất</option></select>
        <select aria-label="Mức ưu tiên" className={staffField} value={filters.priority} onChange={e => change({ priority: e.target.value })}><option value="all">Mọi mức ưu tiên</option><option value="high">Ưu tiên cao</option></select>
      </div>
      {error && <p role="alert" className="p-3 text-sm text-red-700 dark:text-red-300">{error}</p>}
      <div className="flex items-center justify-between px-4 py-2 text-xs text-slate-500"><span>{result.length} hồ sơ · ưu tiên cao trước, nhận lâu trước</span><button className="text-blue-700 hover:underline dark:text-blue-300" onClick={() => change({ q: "", type: "all", status: "active", priority: "all" })}>Đặt lại bộ lọc</button></div>
      <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-800"><tr>{["Hồ sơ", "Sinh viên", "Nội dung yêu cầu", "Trạng thái", "Ưu tiên", "Tiếp nhận"].map(label => <th scope="col" key={label} className="px-4 py-3 font-medium">{label}</th>)}</tr></thead><tbody>{visible.map(ticket => <tr key={ticket.id} className="border-t border-slate-100 align-top hover:bg-blue-50/40 dark:border-slate-800 dark:hover:bg-slate-800/50"><td className="px-4 py-3"><Link id={`queue-ticket-${ticket.id}`} onClick={() => currentUser && rememberQueuePosition(currentUser.id, `queue-ticket-${ticket.id}`)} href={`/tickets/${encodeURIComponent(ticket.id)}`} className="whitespace-nowrap font-medium text-blue-700 hover:underline dark:text-blue-300">{ticket.code}</Link><p className="mt-1 text-xs text-slate-500">{ticketTypeLabels[ticket.type]}</p></td><td className="px-4 py-3"><p className="whitespace-nowrap">{ticket.studentName}</p><p className="mt-1 text-xs text-slate-500">{ticket.studentMssv}</p></td><td className="max-w-sm px-4 py-3"><Link onClick={() => currentUser && rememberQueuePosition(currentUser.id, `queue-ticket-${ticket.id}`)} href={`/tickets/${encodeURIComponent(ticket.id)}`} className="line-clamp-2 hover:text-blue-700">{ticket.title}</Link></td><td className="px-4 py-3"><StatusBadge status={ticket.status} /></td><td className="px-4 py-3"><span title={ticket.priorityReason} className={ticket.priority === "high" ? "whitespace-nowrap font-medium text-amber-700 dark:text-amber-300" : "whitespace-nowrap text-slate-500"}>{ticket.priority === "high" ? "Ưu tiên cao" : "Bình thường"}</span></td><td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">{formatDate(ticket.createdAt, "Asia/Bangkok")}</td></tr>)}</tbody></table></div>
      {hydrated && !result.length && <div className="p-10 text-center"><h2 className="font-medium">{tickets.length ? "Không có hồ sơ khớp bộ lọc" : "Chưa có hồ sơ"}</h2><p className="mt-2 text-sm text-slate-500">{tickets.length ? "Thử tìm từ khóa khác hoặc đặt lại bộ lọc." : "Hồ sơ mới sẽ xuất hiện khi sinh viên gửi yêu cầu."}</p></div>}
      <footer className="flex items-center justify-between gap-3 border-t border-slate-200 p-3 text-xs dark:border-slate-800"><span>{result.length ? `${(page - 1) * 20 + 1}–${Math.min(page * 20, result.length)}` : "0"} / {result.length} hồ sơ</span><div className="flex items-center gap-3"><button className={staffButton} disabled={page === 1} onClick={() => change({ page: page - 1 })}>Trước</button><span>Trang {page}/{pages}</span><button className={staffButton} disabled={page === pages} onClick={() => change({ page: page + 1 })}>Sau</button></div></footer>
    </section>
  </StaffShell>;
}
