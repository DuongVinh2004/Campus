"use client";

import React, { useCallback, useEffect, useState } from "react";
import { announcementsApi, type AnnouncementStats, type AnnouncementSummary, type WithdrawPreview } from "../../lib/announcements-api";

const STATUS: Record<string, string> = {
  DRAFT: "Bản nháp", PENDING_APPROVAL: "Chờ duyệt", SCHEDULED: "Đã hẹn giờ", PUBLISHING: "Đang phát", PUBLISHED: "Đã phát hành",
  WITHDRAWN: "Đã thu hồi", EXPIRED: "Hết hạn",
};

function message(error: unknown): string {
  return error instanceof Error && error.message ? error.message : "Không thực hiện được. Hãy thử lại.";
}

function Stats({ id }: { id: string }) {
  const [stats, setStats] = useState<AnnouncementStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { announcementsApi.stats(id).then(setStats).catch(e => setError(message(e))); }, [id]);
  if (error) return <p role="alert">{error}</p>;
  if (!stats) return <p role="status">Đang tải số liệu…</p>;
  const rows = (label: string, items: AnnouncementStats["by_faculty"]) => items.length > 0 && (
    <table>
      <caption>{label}</caption>
      <thead><tr><th scope="col">Nhóm</th><th scope="col">Đã gửi</th><th scope="col">Đã đọc</th><th scope="col">Đã xác nhận</th></tr></thead>
      <tbody>{items.map(r => <tr key={r.key}><th scope="row">{r.key === "khác" ? "Nhóm nhỏ (gộp)" : r.key}</th><td>{r.delivered}</td><td>{r.read}</td><td>{r.acked}</td></tr>)}</tbody>
    </table>
  );
  return (
    <div className="space-y-1">
      <p>Đã gửi {stats.delivered} · đã đọc {stats.read} ({Math.round(stats.read_rate * 100)}%) · đã xác nhận {stats.acked}</p>
      {rows("Theo khoa", stats.by_faculty ?? [])}
      {rows("Theo khóa", stats.by_cohort ?? [])}
      <p><small>Nhóm dưới 5 người được gộp vào "Nhóm nhỏ" để không lộ từng người.</small></p>
    </div>
  );
}

function Withdraw({ item, onDone }: { item: AnnouncementSummary; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [preview, setPreview] = useState<WithdrawPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="space-y-1">
      <label>Lý do thu hồi<input value={reason} maxLength={300} onChange={e => setReason(e.target.value)} /></label>
      <button type="button" disabled={reason.trim().length < 5} onClick={async () => {
        setError(null);
        try { setPreview(await announcementsApi.withdrawPreview(item.id, reason.trim())); } catch (e) { setError(message(e)); }
      }}>Xem trước khi thu hồi</button>
      {preview && (
        <div role="dialog" aria-label="Xác nhận thu hồi thông báo">
          <p>Thu hồi <strong>{item.title}</strong>: {preview.summary.delivered} người đã nhận sẽ thấy thông báo là đã thu hồi
            {preview.summary.knowledge_revoked ? "; bản trong kho tri thức cũng được gỡ" : ""}.</p>
          <button type="button" onClick={async () => {
            try { await announcementsApi.withdrawConfirm(preview.preview_id, preview.confirmation_token); setPreview(null); onDone(); } catch (e) { setError(message(e)); }
          }}>Xác nhận thu hồi</button>
          <button type="button" onClick={() => setPreview(null)}>Hủy</button>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}

function Revise({ item, onDone }: { item: AnnouncementSummary; onDone: () => void }) {
  const [title, setTitle] = useState(item.title);
  const [body, setBody] = useState("");
  const [note, setNote] = useState("");
  const [material, setMaterial] = useState(false);
  const [preview, setPreview] = useState<{ preview_id: string; confirmation_token: string; summary: { material: boolean; revision: number } } | null>(null);
  const [error, setError] = useState<string | null>(null);
  return (
    <fieldset className="space-y-1">
      <legend>Sửa thông báo đã gửi</legend>
      <label>Tiêu đề<input value={title} maxLength={200} onChange={e => setTitle(e.target.value)} /></label>
      <label>Nội dung mới (để trống nếu giữ nguyên)<textarea value={body} rows={4} onChange={e => setBody(e.target.value)} /></label>
      <label>Ghi chú thay đổi (người nhận sẽ thấy)<input value={note} maxLength={300} onChange={e => setNote(e.target.value)} /></label>
      <label><input type="checkbox" checked={material} onChange={e => setMaterial(e.target.checked)} /> Thay đổi quan trọng (báo lại cho người đã nhận)</label>
      <button type="button" disabled={note.trim().length < 5} onClick={async () => {
        setError(null);
        const changes = { change_note: note.trim(), material, ...(title.trim() !== item.title ? { title: title.trim() } : {}), ...(body.trim() ? { body: body.trim() } : {}) };
        try { setPreview(await announcementsApi.revisionPreview(item.id, changes)); } catch (e) { setError(message(e)); }
      }}>Xem trước bản sửa</button>
      {preview && (
        <div role="dialog" aria-label="Xác nhận sửa thông báo">
          <p>Lưu thành lần cập nhật {preview.summary.revision}{preview.summary.material ? "; người đã nhận sẽ được báo lại" : ""}.</p>
          <button type="button" onClick={async () => {
            try { await announcementsApi.revisionConfirm(preview.preview_id, preview.confirmation_token); setPreview(null); onDone(); } catch (e) { setError(message(e)); }
          }}>Xác nhận sửa</button>
          <button type="button" onClick={() => setPreview(null)}>Hủy</button>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
    </fieldset>
  );
}

function Approval({ item, onDone }: { item: AnnouncementSummary; onDone: () => void }) {
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const act = async (approve: boolean) => {
    setError(null);
    try { await (approve ? announcementsApi.approve : announcementsApi.reject)(item.id, note.trim(), item.row_version); onDone(); }
    catch (e) { setError(message(e)); }
  };
  return (
    <li>
      <strong>{item.title}</strong> · {item.issuer_unit} · {item.priority === "URGENT" ? "Khẩn" : item.priority === "IMPORTANT" ? "Quan trọng" : "Thường"}
      <label>Ghi chú của người duyệt<input value={note} maxLength={300} onChange={e => setNote(e.target.value)} /></label>
      <button type="button" onClick={() => void act(true)}>Duyệt</button>
      <button type="button" disabled={note.trim().length < 5} onClick={() => void act(false)}>Từ chối</button>
      {error && <p role="alert">{error}</p>}
    </li>
  );
}

/** For announcement authors and approvers: what they sent with reach numbers, withdraw with a confirm step, and the approval queue. */
export function AnnouncementManager() {
  const [authored, setAuthored] = useState<AnnouncementSummary[] | null>(null);
  const [approvals, setApprovals] = useState<AnnouncementSummary[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    announcementsApi.authored().then(r => setAuthored(r.items)).catch(e => setError(message(e)));
    announcementsApi.approvals().then(r => setApprovals(r.items)).catch(() => setApprovals([]));   // 403 for authors who do not approve
  }, []);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="space-y-6">
      {approvals.length > 0 && (
        <section aria-label="Chờ duyệt">
          <h2>Chờ duyệt ({approvals.length})</h2>
          <ul>{approvals.map(item => <Approval key={item.id} item={item} onDone={load} />)}</ul>
        </section>
      )}
      <section aria-label="Thông báo đã soạn">
        <h2>Thông báo đã soạn</h2>
        {error && <p role="alert">{error}</p>}
        {!authored ? <p role="status">Đang tải…</p> : authored.length === 0 ? <p>Chưa có thông báo nào.</p> : (
          <ul>{authored.map(item => (
            <li key={item.id}>
              <strong>{item.title}</strong> · {item.code} · {STATUS[item.status] ?? item.status}
              {["PUBLISHED", "WITHDRAWN", "EXPIRED"].includes(item.status) && (
                <button type="button" aria-expanded={open === item.id} onClick={() => setOpen(open === item.id ? null : item.id)}>Số liệu và thao tác</button>
              )}
              {open === item.id && (
                <div className="space-y-2">
                  <Stats id={item.id} />
                  {item.status === "PUBLISHED" && <Revise item={item} onDone={() => { setOpen(null); load(); }} />}
                  {item.status === "PUBLISHED" && <Withdraw item={item} onDone={() => { setOpen(null); load(); }} />}
                </div>
              )}
            </li>
          ))}</ul>
        )}
      </section>
    </div>
  );
}
