"use client";

import React, { useEffect, useMemo, useState } from "react";
import { announcementsApi, type AnnouncementSummary, type Audience, type AudienceCount, type PublishPreview } from "../../lib/announcements-api";

const ROLES = [["STUDENT", "Sinh viên"], ["LECTURER", "Giảng viên"], ["SUPPORT_OFFICER", "Cán bộ"]];
const CATEGORIES = [["ACADEMIC", "Học vụ"], ["EXAM", "Thi"], ["FINANCE", "Học phí"], ["STUDENT_AFFAIRS", "Công tác sinh viên"], ["FACILITIES", "Cơ sở vật chất"], ["EVENT", "Sự kiện"], ["SYSTEM", "Hệ thống"]];

const split = (text: string) => text.split(",").map(s => s.trim()).filter(Boolean);
const message = (error: unknown) => (error instanceof Error ? error.message : "Không thực hiện được.");

const LABEL = "block text-sm font-medium text-[var(--text-primary)]";
const FIELD = "fluent-input mt-1 block w-full px-3 py-2";
const CHECK = "inline-flex items-center gap-2 text-sm";

export function AnnouncementCompose() {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [category, setCategory] = useState("ACADEMIC");
  const [priority, setPriority] = useState<"NORMAL" | "IMPORTANT" | "URGENT">("NORMAL");
  const [roles, setRoles] = useState<string[]>([]);
  const [faculties, setFaculties] = useState("");
  const [classes, setClasses] = useState("");
  const [everyone, setEveryone] = useState(false);
  const [expires, setExpires] = useState("");
  const [count, setCount] = useState<AudienceCount | null>(null);
  const [preview, setPreview] = useState<PublishPreview | null>(null);
  const [draftId, setDraftId] = useState<string | null>(null);
  const [mine, setMine] = useState<AnnouncementSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const audience: Audience = useMemo(() => ({
    groups: [everyone ? {} : { roles, faculty_codes: split(faculties), class_codes: split(classes) }],
  }), [everyone, roles, faculties, classes]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      announcementsApi.audienceCount(audience).then(setCount).catch(() => setCount(null));
    }, 400);
    return () => window.clearTimeout(handle);
  }, [audience]);
  useEffect(() => { announcementsApi.authored().then(r => setMine(r.items)).catch(() => undefined); }, [notice]);

  const toggleRole = (role: string) => setRoles(current => current.includes(role) ? current.filter(r => r !== role) : [...current, role]);

  const makePreview = async () => {
    setError(null);
    try {
      const created = await announcementsApi.createDraft({ title, body, category, priority, audience, expires_at: new Date(expires).toISOString() });
      setDraftId(created.id);
      setPreview(await announcementsApi.publishPreview(created.id));
    } catch (e) { setError(message(e)); }
  };
  const send = async () => {
    if (!preview) return;
    try {
      const result = await announcementsApi.publishConfirm(preview.preview_id, preview.confirmation_token);
      setNotice(result.status === "PENDING_APPROVAL" ? "Đã gửi, đang chờ người thứ hai duyệt." : result.status === "SCHEDULED" ? "Đã hẹn giờ gửi." : "Đã gửi thông báo.");
      setPreview(null); setDraftId(null); setTitle(""); setBody("");
    } catch (e) { setError(message(e)); }
  };

  return (
    <section className="campus-card max-w-3xl space-y-4 p-4 sm:p-6" aria-label="Soạn thông báo">
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      <label className={LABEL}>Tiêu đề<input className={FIELD} value={title} onChange={e => setTitle(e.target.value)} maxLength={200} /></label>
      <label className={LABEL}>Nội dung<textarea className={FIELD} value={body} onChange={e => setBody(e.target.value)} rows={6} maxLength={10000} /></label>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className={LABEL}>Loại
          <select className={FIELD} value={category} onChange={e => setCategory(e.target.value)}>{CATEGORIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        </label>
        <label className={LABEL}>Mức độ
          <select className={FIELD} value={priority} onChange={e => setPriority(e.target.value as typeof priority)}>
            <option value="NORMAL">Thường</option><option value="IMPORTANT">Quan trọng</option><option value="URGENT">Khẩn</option>
          </select>
        </label>
      </div>
      <fieldset className="space-y-3 rounded-xl border border-[var(--border-color)] p-4">
        <legend className="px-1 text-sm font-semibold">Đối tượng nhận</legend>
        <div className="flex flex-wrap gap-x-5 gap-y-2">
          <label className={CHECK}><input type="checkbox" checked={everyone} onChange={e => setEveryone(e.target.checked)} /> Toàn trường</label>
          {!everyone && ROLES.map(([v, l]) => <label key={v} className={CHECK}><input type="checkbox" checked={roles.includes(v)} onChange={() => toggleRole(v)} /> {l}</label>)}
        </div>
        {!everyone && (
          <div className="grid gap-4 sm:grid-cols-2">
            <label className={LABEL}>Khoa (cách nhau bằng dấu phẩy)<input className={FIELD} value={faculties} onChange={e => setFaculties(e.target.value)} /></label>
            <label className={LABEL}>Lớp (cách nhau bằng dấu phẩy)<input className={FIELD} value={classes} onChange={e => setClasses(e.target.value)} /></label>
          </div>
        )}
        <p className="text-sm text-[var(--text-secondary)]" role="status" aria-live="polite">{count ? `Sẽ gửi cho ${count.total} người${count.warnings.includes("LARGE_AUDIENCE") ? " (nhóm lớn)" : ""}${count.total === 0 ? " — chưa có người nhận" : ""}.` : "Đang tính số người nhận…"}</p>
      </fieldset>
      <label className={LABEL}>Hết hạn lúc<input className={FIELD} type="datetime-local" value={expires} onChange={e => setExpires(e.target.value)} /></label>
      {!preview && <button className="fluent-btn-primary" disabled={!title || !body || !expires} onClick={() => void makePreview()}>Xem trước khi gửi</button>}
      {preview && (
        <div role="dialog" aria-label="Xác nhận gửi" className="space-y-3 rounded-xl border border-[var(--border-color)] bg-[var(--surface-subtle)] p-4">
          <p>Gửi cho {preview.summary.total} người{preview.summary.needs_approval ? " — cần người thứ hai duyệt" : ""}.</p>
          {preview.warnings.map(w => <p key={w}>Cảnh báo: {w}</p>)}
          <div className="flex flex-wrap gap-2">
            <button className="fluent-btn-primary" onClick={() => void send()}>Xác nhận gửi</button>
            <button className="fluent-btn-secondary" onClick={() => { setPreview(null); }}>Quay lại sửa</button>
          </div>
          <span hidden>{draftId}</span>
        </div>
      )}
      <h3>Thông báo của tôi</h3>
      {mine.length === 0 ? <p>Chưa có thông báo nào.</p> : <ul>{mine.map(m => <li key={m.id}>{m.code} · {m.title} · {m.status}</li>)}</ul>}
    </section>
  );
}
