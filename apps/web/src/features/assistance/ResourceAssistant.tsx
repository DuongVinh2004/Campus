"use client";

import { useEffect, useState } from "react";
import { useUnifiedAssistant } from "@/lib/unified-assistant-runtime";
import type { SurfaceContext } from "@/lib/assistant-state-service";
import { UnifiedAssistantWorkspace } from "./UnifiedAssistantWorkspace";
import { AccessibleDialog } from "@/components/shared/AccessibleDialog";

export function ResourceAssistant({ id, version, surface }: { id: string; version: number; surface: "service" | "certificate" }) {
  const runtime = useUnifiedAssistant();
  const [open, setOpen] = useState(false);
  const [staffSurface, setStaffSurface] = useState<NonNullable<SurfaceContext["staff_surface"]>>("detail");
  const [staffIntent, setStaffIntent] = useState<NonNullable<SurfaceContext["staff_intent"]>>("read");
  const resource = { kind: surface === "service" ? "service_request" as const : "certificate_request" as const, id, expected_version: version };
  useEffect(() => { runtime.setSurface({ surface, resource });
    return () => runtime.setSurface({ surface: "chat" });
  }, [id, version, surface]);
  const fields: Array<[NonNullable<SurfaceContext["field"]>, string]> = surface === "service"
    ? [["reason", "Lý do"], ["course_record_id", "Học phần"], ["contact_preference", "Kênh thông tin"]]
    : [["purpose", "Mục đích"], ["recipient", "Nơi nhận"], ["quantity", "Số bản"], ["delivery_method", "Cách nhận"]];
  function ask(field?: SurfaceContext["field"]) {
    const scope: SurfaceContext = { surface, resource, ...(field ? { field } : {}),
      ...(runtime.capabilities?.audience === "staff" ? { staff_surface: staffSurface, staff_intent: staffIntent } : {}) };
    runtime.setSurface(scope); setOpen(true);
    void runtime.send(field ? `Giải thích trường ${fields.find(item => item[0] === field)?.[1]}` : "Đối chiếu hồ sơ đang mở", scope);
  }
  return <div className="mt-3 space-y-2"><p className="text-xs">Context chỉ gửi mã hồ sơ, phiên bản và mã trường; nội dung chưa lưu và notes riêng được giữ ngoài context.</p>
    {runtime.capabilities?.audience === "staff" && <div className="flex gap-3"><label>Khu vực<select value={staffSurface} onChange={e => setStaffSurface(e.target.value as typeof staffSurface)}>{["queue", "detail", "checklist", "editor", "error", "handover", "admin"].map(v => <option key={v}>{v}</option>)}</select></label>
      <label>Ý định<select value={staffIntent} onChange={e => setStaffIntent(e.target.value as typeof staffIntent)}>{["read", "review", "prepare", "retry", "route", "publish"].map(v => <option key={v}>{v}</option>)}</select></label></div>}
    <div className="flex flex-wrap gap-2"><button type="button" className="fluent-btn-secondary" disabled={runtime.busy} onClick={() => ask()}>Mở trợ lý chung</button>{runtime.capabilities?.audience !== "staff" && fields.map(([field, label]) => <button type="button" key={field} className="fluent-btn-secondary" disabled={runtime.busy} onClick={() => ask(field)}>Giải thích: {label}</button>)}</div>
    <AccessibleDialog open={open} onClose={() => setOpen(false)} labelledBy="resource-assistant-title" className="fixed inset-3 flex min-h-0 flex-col bg-white dark:bg-slate-950 lg:left-auto lg:w-[620px]"><header className="flex items-center justify-between p-3"><h2 id="resource-assistant-title">Trợ lý hồ sơ · phiên bản {version}</h2><button type="button" onClick={() => setOpen(false)} className="fluent-btn-secondary">Đóng</button></header><UnifiedAssistantWorkspace compact /></AccessibleDialog>
  </div>;
}
