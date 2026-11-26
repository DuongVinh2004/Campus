"use client";

import React, { useCallback, useEffect, useState } from "react";
import { announcementsApi, type AnnouncementDetail, type AnnouncementSummary } from "../../lib/announcements-api";

type Filter = "active" | "unread" | "all";

function message(error: unknown): string {
  return error instanceof Error ? error.message : "Không tải được thông báo.";
}

function PriorityBadge({ priority }: { priority: string }) {
  if (priority === "URGENT") return <strong className="campus-badge">Khẩn</strong>;
  if (priority === "IMPORTANT") return <span className="campus-badge">Quan trọng</span>;
  return null;
}

function domain(url: string): string {
  try { return new URL(url).hostname; } catch { return ""; }
}

export function AnnouncementDetailView({ id, onBack }: { id: string; onBack: () => void }) {
  const [item, setItem] = useState<AnnouncementDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [acking, setAcking] = useState(false);

  useEffect(() => {
    announcementsApi.get(id).then(setItem).catch(e => setError(message(e)));
  }, [id]);

  if (error) return <p role="alert">{error}</p>;
  if (!item) return <p role="status">Đang tải thông báo…</p>;
  const confirm = async () => {
    setAcking(true);
    try {
      await announcementsApi.ack(id);
      setItem({ ...item, needs_ack: false, acked: true });
    } catch (e) { setError(message(e)); } finally { setAcking(false); }
  };
  return (
    <article className="campus-card space-y-3 p-4 sm:p-6" aria-labelledby="ann-title">
      <button className="fluent-btn-ghost text-sm" onClick={onBack}>← Về danh sách</button>
      <h2 id="ann-title" className="text-lg font-semibold">{item.title}</h2>
      <p><PriorityBadge priority={item.priority} /> {item.issuer_unit} · {item.code}{item.source_ref?.document_no ? ` · Văn bản ${item.source_ref.document_no}` : ""}</p>
      <div style={{ whiteSpace: "pre-wrap" }}>{item.body}</div>
      {item.revision > 1 && <p>Cập nhật lần {item.revision}{item.revisions?.length ? `: ${item.revisions[item.revisions.length - 1].change_note}` : ""}</p>}
      {item.links.length > 0 && (
        <ul>{item.links.map((link, i) => link.url ? (
          <li key={i}><a href={link.url} rel="noopener noreferrer" target="_blank">{link.label}</a> ({domain(link.url)})</li>) : <li key={i}>{link.label}</li>)}</ul>
      )}
      <p>Hết hiệu lực: {new Date(item.expires_at).toLocaleString("vi-VN")}</p>
      {item.viewer === "recipient" && item.requires_ack && (item.needs_ack ? (
        <>
          <button className="fluent-btn-primary" disabled={acking} onClick={() => void confirm()} aria-describedby="ack-deadline">Tôi đã đọc và hiểu</button>
          <p id="ack-deadline">Hạn xác nhận: {item.ack_deadline ? new Date(item.ack_deadline).toLocaleString("vi-VN") : "—"}</p>
        </>
      ) : <p role="status">Bạn đã xác nhận đã đọc và hiểu.</p>)}
    </article>
  );
}

export function AnnouncementInbox({ initialId = null, publicOnly = false }: { initialId?: string | null; publicOnly?: boolean }) {
  const [filter, setFilter] = useState<Filter>("active");
  const [items, setItems] = useState<AnnouncementSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(initialId);

  const load = useCallback(() => {
    setItems(null);
    const request = publicOnly ? announcementsApi.publicList() : announcementsApi.mine(filter);
    request.then(r => { setItems(r.items); setError(null); }).catch(e => setError(message(e)));
  }, [filter, publicOnly]);
  useEffect(() => { load(); }, [load]);

  if (openId) return <AnnouncementDetailView id={openId} onBack={() => { setOpenId(null); load(); }} />;
  return (
    <section className="space-y-3" aria-label="Thông báo">
      {!publicOnly && (
        <div role="tablist" className="flex flex-wrap gap-2">
          {([["active", "Đang hiệu lực"], ["unread", "Chưa đọc"], ["all", "Tất cả"]] as [Filter, string][]).map(([value, label]) => (
            <button key={value} role="tab" aria-selected={filter === value} onClick={() => setFilter(value)}
              className="min-h-9 rounded-full border border-[var(--border-color)] px-4 text-sm aria-selected:border-[var(--color-primary)] aria-selected:bg-[var(--color-primary-subtle)] aria-selected:font-semibold">{label}</button>
          ))}
        </div>
      )}
      {error && <p role="alert">{error}</p>}
      {!error && items === null && <p role="status">Đang tải…</p>}
      {items !== null && items.length === 0 && <p>Chưa có thông báo nào.</p>}
      <ul className="space-y-2">
        {(items ?? []).map(item => (
          <li key={item.id} className="campus-card p-3">
            <button className="w-full text-left font-medium" onClick={() => setOpenId(item.id)} aria-label={item.title}>
              <PriorityBadge priority={item.priority} /> {!item.read && !publicOnly && <span className="campus-badge">Mới</span>} {item.title}
            </button>
            <div className="mt-1 text-xs text-[var(--text-secondary)]">{item.issuer_unit} · hết hạn {new Date(item.expires_at).toLocaleDateString("vi-VN")}{item.requires_ack ? (item.acked ? " · Đã xác nhận" : " · Cần xác nhận") : ""}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}
