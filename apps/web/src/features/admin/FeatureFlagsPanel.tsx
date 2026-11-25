"use client";

import React, { useCallback, useEffect, useState } from "react";
import { featuresApi, type FeatureAdminList, type FeatureAuditRow, type FeatureItem, type FeaturePreview } from "../../lib/features-api";

type Filter = "all" | "off" | "override" | "restart";

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "Không thực hiện được. Thử lại sau.";
}

function statusLabel(item: FeatureItem): string {
  if (item.locked) return "Luôn bật";
  return item.effective_for_all ? "Bật" : "Tắt";
}

export function FeatureFlagsPanel() {
  const [data, setData] = useState<FeatureAdminList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [tab, setTab] = useState<"flags" | "history">("flags");
  const [audit, setAudit] = useState<FeatureAuditRow[]>([]);
  const [editing, setEditing] = useState<FeatureItem | null>(null);
  const [reason, setReason] = useState("");
  const [target, setTarget] = useState<string>("false");
  const [preview, setPreview] = useState<FeaturePreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await featuresApi.adminList());
      setError(null);
    } catch (e) {
      setError(errorText(e));
    }
  }, []);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (tab !== "history") return;
    featuresApi.audit().then(r => setAudit(r.items)).catch(e => setError(errorText(e)));
  }, [tab, data?.version]);

  const close = () => { setEditing(null); setPreview(null); setReason(""); };

  const startPreview = async (remove = false) => {
    if (!editing || !data) return;
    setBusy(true);
    try {
      const value: boolean | string = editing.variants.length ? target : target === "true";
      setPreview(await featuresApi.preview(editing.key, { value: remove ? undefined : value, reason, expected_version: data.version, remove }));
      setError(null);
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  };

  const confirm = async () => {
    if (!preview) return;
    setBusy(true);
    try {
      await featuresApi.confirm(preview.preview_id, preview.confirmation_token, `ff-${preview.preview_id}`);
      setNotice("Đã lưu thay đổi. Dữ liệu của tính năng được giữ nguyên.");
      close();
      await load();
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  };

  if (!data) {
    return <div className="campus-card" role="status">{error ?? "Đang tải danh sách tính năng…"}</div>;
  }
  const items = data.items.filter(item =>
    filter === "off" ? !item.effective_for_all : filter === "override" ? item.configured.source === "override"
      : filter === "restart" ? item.off_reasons.includes("NOT_WIRED_RESTART_REQUIRED") : true);
  const areas = Array.from(new Set(items.map(i => i.area)));

  return (
    <section className="space-y-4" aria-label="Cờ tính năng">
      {error && <p role="alert" className="campus-alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {data.store_error && <p role="alert">Không đọc được kho cờ; đang dùng giá trị đã biết cuối cùng.</p>}
      <div role="tablist" className="flex gap-2">
        <button role="tab" aria-selected={tab === "flags"} onClick={() => setTab("flags")}>Tính năng</button>
        <button role="tab" aria-selected={tab === "history"} onClick={() => setTab("history")}>Lịch sử</button>
      </div>
      {tab === "history" ? (
        audit.length === 0 ? <p>Chưa có thay đổi nào.</p> : (
          <ul>{audit.map(row => (
            <li key={row.id}>{row.at} · {row.key} → {row.after.removed ? "gỡ ghi đè" : String(row.after.value)} · {row.reason}</li>
          ))}</ul>
        )
      ) : (
        <>
          <label>Lọc{" "}
            <select value={filter} onChange={e => setFilter(e.target.value as Filter)}>
              <option value="all">Tất cả</option><option value="off">Đang tắt</option>
              <option value="override">Có ghi đè</option><option value="restart">Cần khởi động lại</option>
            </select>
          </label>
          {items.length === 0 && <p>Không có tính năng nào khớp bộ lọc.</p>}
          {areas.map(area => (
            <div key={area}>
              <h3>{area}</h3>
              <table className="campus-table">
                <thead><tr><th>Tính năng</th><th>Trạng thái</th><th>Nguồn</th><th>Lối vào</th><th /></tr></thead>
                <tbody>{items.filter(i => i.area === area).map(item => (
                  <tr key={item.key}>
                    <td>{item.title}<br /><code>{item.key}</code></td>
                    <td>{statusLabel(item)}{item.off_reasons.length > 0 && !item.locked ? ` (${item.off_reasons.join(", ")})` : ""}</td>
                    <td>{item.configured.source}</td>
                    <td>{[...item.entry_points.pages.map(p => "/" + p), ...item.entry_points.jobs].join(", ") || "—"}</td>
                    <td>{item.locked ? null : (
                      <button onClick={() => { setEditing(item); setPreview(null); setTarget(item.variants.length ? item.variants[0] : String(!item.effective_for_all)); }}>Đổi</button>
                    )}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          ))}
        </>
      )}
      {editing && (
        <div role="dialog" aria-modal="true" aria-label={`Đổi ${editing.title}`} className="campus-card">
          <h3>Đổi: {editing.title}</h3>
          {editing.variants.length ? (
            <select aria-label="Giá trị" value={target} onChange={e => setTarget(e.target.value)}>{editing.variants.map(v => <option key={v}>{v}</option>)}</select>
          ) : (
            <select aria-label="Giá trị" value={target} onChange={e => setTarget(e.target.value)}><option value="true">Bật</option><option value="false">Tắt</option></select>
          )}
          <label>Lý do (ít nhất 10 ký tự)
            <input value={reason} onChange={e => setReason(e.target.value)} maxLength={300} />
          </label>
          {preview && (
            <div role="status">
              <p>Dữ liệu được giữ nguyên.</p>
              {preview.impact.also_off.length > 0 && <p>Cũng bị tắt theo: {preview.impact.also_off.join(", ")}</p>}
              {preview.impact.restart_required && <p>Cần khởi động lại để tính năng này được dựng.</p>}
            </div>
          )}
          <div className="flex gap-2">
            {!preview && <button disabled={busy || reason.trim().length < 10} onClick={() => void startPreview()}>Xem trước</button>}
            {!preview && editing.configured.source === "override" && <button disabled={busy || reason.trim().length < 10} onClick={() => void startPreview(true)}>Gỡ ghi đè</button>}
            {preview && <button disabled={busy} onClick={() => void confirm()}>Xác nhận</button>}
            <button onClick={close}>Hủy</button>
          </div>
        </div>
      )}
    </section>
  );
}
