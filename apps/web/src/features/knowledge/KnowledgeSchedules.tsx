"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { usePolling } from "@/lib/use-polling";
import { ApiClient } from "../../lib/api/client";

type Schedule = { id: string; kind: "URL_REFRESH" | "RELEASE_DUE"; target_id: string; state: string; can_resume?: boolean;
  not_before: string; expires_at: string; interval_seconds: number;
  last_outcome: { state: string; code?: string; release_id?: string } | null };
type ScheduleState = { items: Schedule[]; session_expires_at: string; background_running: boolean };
type Intake = { id: string; filename: string; can_refresh_url?: boolean; original_sha256: string };
const base = "/v1/knowledge/platform/schedules";
const labels: Record<string, string> = { ACTIVE: "Đang theo dõi trong phiên", SESSION_REQUIRED: "Cần tiếp tục bằng đúng phiên đã cấu hình",
  EXPIRED: "Đã hết thời hạn", CANCELLED: "Đã dừng lịch", QUEUED: "Đã tạo hồ sơ kiểm tra URL",
  WAITING_FOR_JOB: "Đang chờ job trước", AWAITING_CONFIRMATION: "Đã tới hạn, cần xem trước và xác nhận",
  BLOCKED: "Cần đối chiếu lại căn cứ" };

function localTime(date: Date) {
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

export function KnowledgeSchedules({ releases, generation, onPreview }: {
  releases: Array<{ id: string; document_count: number }>; generation: number;
  onPreview: (releaseId: string) => Promise<void>;
}) {
  const [state, setState] = useState<ScheduleState | null>(null);
  const [intakes, setIntakes] = useState<Intake[]>([]);
  const [kind, setKind] = useState<"URL_REFRESH" | "RELEASE_DUE">("URL_REFRESH");
  const [target, setTarget] = useState("");
  const [first, setFirst] = useState(() => localTime(new Date(Date.now() + 60_000)));
  const [until, setUntil] = useState(() => localTime(new Date(Date.now() + 20 * 60_000)));
  const [interval, setIntervalMinutes] = useState(15);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const requestKey = useRef<string | null>(null);
  const refresh = useCallback(async () => {
    const [next, sources] = await Promise.all([new ApiClient().get<ScheduleState>(base),
      new ApiClient().get<{ items: Intake[] }>("/v1/knowledge/platform/intakes")]);
    setState(next); setIntakes((sources.items || []).filter(item => item.can_refresh_url));
  }, []);
  usePolling(async () => { try { await refresh(); } catch (e) { setError((e as Error).message); } }, 15_000, [refresh]);
  async function run(action: () => Promise<void>) {
    setBusy(true); setError("");
    try { await action(); await refresh(); } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <section className="campus-panel space-y-3" aria-label="Lịch đồng bộ và hiệu lực">
    <h2 className="font-semibold">Lịch đồng bộ và hiệu lực</h2>
    <p className="text-sm">Lịch chạy nền khi phiên đăng nhập còn hiệu lực, kể cả khi đóng tab. Kiểm URL giữ từng hồ sơ nguồn;
      lịch hiệu lực báo sẵn sàng để xem trước và xác nhận phát hành.</p>
    {state && <p className="text-sm">Phiên hết hạn {new Date(state.session_expires_at).toLocaleString("vi-VN")}.
      {!state.background_running && " Bộ chạy nền chưa hoạt động trên phiên ứng dụng này."}</p>}
    {error && <p role="alert">{error}</p>}
    <form className="space-y-3" onChange={() => { requestKey.current = null; }} onSubmit={event => {
      event.preventDefault();
      void run(async () => {
        const original = intakes.find(item => item.id === target);
        requestKey.current ||= crypto.randomUUID();
        await new ApiClient().post(base, { kind, target_id: target, not_before: new Date(first).toISOString(),
          expires_at: new Date(until).toISOString(), interval_seconds: interval * 60, confirmed,
          ...(kind === "URL_REFRESH" ? { expected_original_sha256: original?.original_sha256 } : { expected_generation: generation }) },
        { "Idempotency-Key": requestKey.current });
        requestKey.current = null; setConfirmed(false);
      });
    }}><fieldset disabled={busy} className="grid gap-3 md:grid-cols-2">
      <label>Loại lịch<select className="fluent-input w-full" value={kind} onChange={e => {
        setKind(e.target.value as typeof kind); setTarget(""); setConfirmed(false);
      }}><option value="URL_REFRESH">Kiểm tra lại URL</option><option value="RELEASE_DUE">Theo dõi ngày hiệu lực release</option></select></label>
      <label>Nguồn hoặc release<select className="fluent-input w-full" required value={target} onChange={e => { setTarget(e.target.value); setConfirmed(false); }}>
        <option value="">Chọn đích cụ thể</option>
        {kind === "URL_REFRESH" ? intakes.map(item => <option key={item.id} value={item.id}>{item.filename} · {item.id.slice(-8)}</option>)
          : releases.map(item => <option key={item.id} value={item.id}>{item.id} · {item.document_count} tài liệu</option>)}
      </select></label>
      <label>Bắt đầu theo dõi<input className="fluent-input w-full" type="datetime-local" required value={first} onChange={e => { setFirst(e.target.value); setConfirmed(false); }} /></label>
      <label>Kết thúc trong phiên hiện tại<input className="fluent-input w-full" type="datetime-local" required value={until}
        max={state ? localTime(new Date(state.session_expires_at)) : undefined} onChange={e => { setUntil(e.target.value); setConfirmed(false); }} /></label>
      {kind === "URL_REFRESH" && <label>Chu kỳ kiểm tra<select className="fluent-input w-full" value={interval} onChange={e => { setIntervalMinutes(Number(e.target.value)); setConfirmed(false); }}>
        <option value={15}>15 phút</option><option value={30}>30 phút</option><option value={60}>60 phút</option>
      </select></label>}
      <label className="md:col-span-2"><input type="checkbox" checked={confirmed} required onChange={e => setConfirmed(e.target.checked)} /> Tôi xác nhận đích, thời gian và phạm vi lịch này.</label>
      <button type="submit" disabled={!target || !confirmed || !state?.background_running} className="fluent-btn-primary">Lưu lịch trong phiên</button>
    </fieldset></form>
    <ul className="space-y-3">{state?.items.map(item => <li key={item.id} className="rounded-xl border p-3 space-y-2">
      <p>{item.kind === "URL_REFRESH" ? "Kiểm URL" : "Theo dõi hiệu lực"} · {labels[item.state] || item.state}</p>
      <p className="break-all text-xs">{item.target_id} · từ {new Date(item.not_before).toLocaleString("vi-VN")} đến {new Date(item.expires_at).toLocaleString("vi-VN")}</p>
      {item.last_outcome && <p role="status">{labels[item.last_outcome.state] || item.last_outcome.state}{item.last_outcome.code ? ` · ${item.last_outcome.code}` : ""}</p>}
      {item.last_outcome?.state === "AWAITING_CONFIRMATION" && item.state === "ACTIVE" && <button disabled={busy} onClick={() => void run(() => onPreview(item.target_id))}>Xem trước release tới hạn</button>}
      {item.state === "SESSION_REQUIRED" && (item.can_resume
        ? <button disabled={busy} onClick={() => void run(async () => { await new ApiClient().post(base + "/resume"); })}>Tiếp tục lịch của phiên</button>
        : <p className="text-sm">Lịch gắn với phiên cũ; cần cấu hình lịch mới trong phiên hiện tại.</p>)}
      {!["CANCELLED", "EXPIRED"].includes(item.state) && <button disabled={busy} onClick={() => void run(async () => { await new ApiClient().post(`${base}/${item.id}/cancel`); })}>Dừng lịch này</button>}
    </li>)}</ul>
  </section>;
}
