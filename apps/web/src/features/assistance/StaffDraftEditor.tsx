"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";

import React, { useEffect, useRef, useState } from "react";
import { ApiClient, ApiClientError } from "../../lib/api/client";
import type { ResourceRef } from "../../lib/unified-ai-contracts";

interface Readback { draft_version: number; business_version: number; text: string; saved: boolean; binding_stale: boolean; actor_id: string; tenant: string }
interface Intent { resource: ResourceRef; text: string; expected_draft_version: number; client_id: string }
interface Buffer { text: string; version: number; savedText: string; dirty: boolean; pending?: Intent; conflict: boolean }
const buffers = new Map<string, Buffer>();
let unloadGuard = false;
const client = () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL });

function clientId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  let stamp = Date.now();
  for (let i = 5; i >= 0; i--) { bytes[i] = stamp % 256; stamp = Math.floor(stamp / 256); }
  bytes[6] = (bytes[6] & 15) | 112; bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function StaffDraftEditor({ actorId, tenant = "huce-local-public", resource, onUse }: {
  actorId: string; tenant?: string; resource: ResourceRef; onUse: (text: string) => void;
}) {
  const key = `${tenant}:${actorId}:${resource.kind}:${resource.id}`;
  const holder = useRef({ key, buffer: buffers.get(key) || { text: "", version: 0, savedText: "", dirty: false, conflict: false } as Buffer });
  if (holder.current.key !== key) holder.current = { key, buffer: buffers.get(key) || { text: "", version: 0, savedText: "", dirty: false, conflict: false } };
  const context = `${key}:${resource.expected_version}`;
  const contextRef = useRef(context); contextRef.current = context;
  const [revision, paint] = useState(0);
  const [authorized, setAuthorized] = useState(false);
  const [authorizationContext, setAuthorizationContext] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [remote, setRemote] = useState<Readback | null>(null);
  const alive = useRef(true);
  const saveLock = useRef(false);
  const b = holder.current.buffer;
  const canEdit = authorized && authorizationContext === context;
  const redraw = () => { if (alive.current) paint(v => v + 1); };
  const check = (value: Readback) => {
    if (value.actor_id !== actorId || value.tenant !== tenant || typeof value.text !== "string" || value.text.length > 8000
      || !Number.isInteger(value.draft_version) || value.draft_version < 0 || typeof value.saved !== "boolean"
      || typeof value.binding_stale !== "boolean" || !Number.isInteger(value.business_version))
      throw new Error("Phiên hoặc danh tính đọc nháp đã thay đổi; cần đăng nhập và đọc lại.");
    return value;
  };

  useEffect(() => {
    alive.current = true;
    if (!unloadGuard) {
      window.addEventListener("beforeunload", event => {
        if (Array.from(buffers.values()).some(item => item.dirty || item.pending)) { event.preventDefault(); event.returnValue = ""; }
      });
      unloadGuard = true;
    }
    let cancelled = false;
    setAuthorized(false); setBusy(false); setError(""); setRemote(null);
    void client().post<Readback>("/v1/assistant/staff-drafts/read", { resource }).then(value => {
      if (cancelled || contextRef.current !== context) return;
      check(value);
      setRemote(value); setAuthorized(true); setAuthorizationContext(context); buffers.set(key, b);
      if (!b.dirty && !b.pending) { b.text = value.text; b.savedText = value.text; b.version = value.draft_version; }
      else if (b.version !== value.draft_version) { b.conflict = true; setError("Bản trên server đã thay đổi; nội dung đang soạn được giữ."); }
      redraw();
    }).catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : "Chưa đọc được nháp"); });
    return () => { cancelled = true; alive.current = false; };
  }, [key, resource.expected_version]);

  async function save() {
    if (!canEdit || busy || saveLock.current || b.conflict) return;
    saveLock.current = true;
    const started = context;
    const active = () => alive.current && contextRef.current === started;
    const intent = b.pending || { resource: { ...resource }, text: b.text, expected_draft_version: b.version, client_id: clientId() };
    b.pending = intent; setBusy(true); setError(""); redraw();
    try {
      const ack = await client().post<{ saved: boolean; draft_version: number; business_version: number; receipt_id: string }>("/v1/assistant/staff-drafts/save", intent);
      if (ack.saved !== true || ack.draft_version !== intent.expected_draft_version + 1 || ack.business_version !== intent.resource.expected_version || !ack.receipt_id)
        throw new Error("Chưa xác minh được receipt lưu nháp");
      b.version = ack.draft_version; b.savedText = intent.text; b.pending = undefined; b.dirty = b.text !== intent.text;
      const latest = check(await client().post<Readback>("/v1/assistant/staff-drafts/read", { resource }));
      if (active()) setRemote(latest);
      if (latest.draft_version > b.version) { b.conflict = true; throw new Error("Nội dung đã được lưu trong lịch sử; bản server có phiên bản mới hơn."); }
    } catch (e) {
      if (e instanceof ApiClientError && e.problem.status === 409) b.conflict = true;
      if (active() && e instanceof ApiClientError && [401, 403, 404].includes(e.problem.status)) setAuthorized(false);
      if (active()) setError(`${e instanceof Error ? e.message : "Chưa xác minh được đã lưu"} Nội dung đang soạn được giữ.`);
    } finally { saveLock.current = false; if (active()) { setBusy(false); redraw(); } }
  }

  useEffect(() => {
    if (!b.dirty || !canEdit || busy || b.conflict || error) return;
    const timer = setTimeout(() => void save(), 600);
    return () => clearTimeout(timer);
  }, [revision, canEdit, busy, error]);

  async function reconcile() {
    const started = context;
    try {
      const value = check(await client().post<Readback>("/v1/assistant/staff-drafts/read", { resource }));
      if (!alive.current || contextRef.current !== started) return;
      setRemote(value); b.version = value.draft_version; b.savedText = value.text; b.pending = undefined; b.conflict = false;
      b.dirty = b.text !== value.text; setAuthorized(true); setAuthorizationContext(started); setError(""); redraw();
    } catch (e) { if (alive.current && contextRef.current === started) setError(e instanceof Error ? e.message : "Chưa đối chiếu được nháp"); }
  }

  async function useText() {
    const started = context;
    try {
      const value = check(await client().post<Readback>("/v1/assistant/staff-drafts/read", { resource }));
      if (value.binding_stale) throw new Error("Hồ sơ/nguồn đã đổi; đối chiếu và lưu nháp theo phiên bản hiện tại trước.");
      if (b.dirty || b.pending || value.draft_version !== b.version || value.text !== b.text)
        throw new Error("Cần lưu và đối chiếu đúng bản nháp server trước khi đưa vào phản hồi; nội dung đang soạn được giữ.");
      if (b.text.length > 1000) throw new Error("Ô phản hồi giới hạn 1.000 ký tự; chọn nội dung phù hợp để chuyển.");
      if (alive.current && contextRef.current === started) onUse(b.text);
    } catch (e) { if (alive.current && contextRef.current === started) setError(e instanceof Error ? e.message : "Chưa kiểm tra được quyền dùng nháp"); }
  }

  return <section aria-label="Nháp riêng cán bộ" className="my-4 space-y-3 rounded-xl border p-4">
    <h3 className="font-semibold">Nháp riêng cán bộ</h3>
    <p className="text-sm">Tự lưu trên server. Nháp chưa gửi cho sinh viên và không hoàn thành kiểm tra bắt buộc.</p>
    <label className="block text-sm">Nội dung nháp riêng<textarea className="fluent-input w-full" maxLength={8000} disabled={!canEdit}
      value={canEdit ? b.text : ""} onChange={e => { b.text = e.target.value; b.dirty = b.text !== b.savedText; buffers.set(key, b); redraw(); }} /></label>
    <p role="status">{busy ? "Đang lưu nháp…" : error ? "Chưa xác minh được bản hiện tại" : b.dirty || b.pending ? "Có nội dung chưa xác minh đã lưu" : b.version > 0 ? `Đã lưu nháp · phiên bản ${b.version}` : "Chưa có nháp đã lưu"}</p>
    {remote?.binding_stale && <p>Hồ sơ hoặc nguồn đã đổi so với bản nháp được lưu; cần đối chiếu.</p>}
    {error && <p role="alert">{error}</p>}
    {canEdit && b.conflict && remote && <details><summary>Bản trên server · phiên bản {remote.draft_version}</summary><pre className="whitespace-pre-wrap">{remote.text}</pre></details>}
    <div className="flex flex-wrap gap-3">
      <button type="button" disabled={!canEdit || busy || b.conflict} onClick={() => void save()}>{b.pending ? "Thử lại cùng nội dung lưu" : "Lưu nháp"}</button>
      {b.conflict && <button type="button" disabled={busy} onClick={() => void reconcile()}>Đối chiếu bản server, giữ nội dung đang soạn</button>}
      <button type="button" disabled={!canEdit || busy || b.conflict || !b.text.trim()} onClick={() => void useText()}>Đưa vào ô phản hồi để kiểm tra</button>
    </div>
  </section>;
}
