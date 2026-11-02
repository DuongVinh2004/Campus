"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";

import React, { useEffect, useRef, useState } from "react";

const base = CAMPUS_API_BASE_URL;
type ResourceKind = "service_request" | "certificate_request";
interface AppliedSource {
  version_id: string; locator: string; source_sha256: string; rendition_sha256: string;
  classification: "synthetic" | "public_snapshot";
  effective_status: "demo_interval" | "unknown"; effective_from: string | null; effective_until: string | null;
}
interface WorkflowPackage {
  schema_version: "unified-workflow.v1";
  resource: { id: string; kind: ResourceKind; version: number; view: "student" | "staff" };
  action_authority: "none";
  classification: "synthetic";
  binding_status: "bound" | "unresolved";
  definition_version: string;
  current_source_differs: boolean;
  readiness: "requires_officer_review" | "undetermined";
  institutional_rules_verified: false;
  binding: null | { workflow_version: string; template_version: string; as_of: string; sha256: string;
    source: AppliedSource; supporting_sources: AppliedSource[]; source_capture_at: string | null };
  supplements: Array<{ sequence: number; at: string | null; binding_status: "bound" | "unresolved";
    source: AppliedSource | null; source_changed_from_submission: boolean | null; reasons: string[] }>;
  template: null | { version: string; title: string };
  mandatory_reviews: Array<{ id: string; label: string; required: true; reviewer: "SUPPORT_OFFICER"; status: "required" }>;
}

function decode(value: unknown, id: string, version: number, kind: ResourceKind): WorkflowPackage {
  const r = value as WorkflowPackage;
  const hash = (v: unknown) => typeof v === "string" && /^[0-9a-f]{64}$/.test(v);
  const text = (v: unknown, limit: number) => typeof v === "string" && v.length > 0 && v.length <= limit;
  const date = (v: unknown) => text(v, 64) && Number.isFinite(Date.parse(v as string));
  const source = (s: AppliedSource | null) => !!s && text(s.version_id, 100) && text(s.locator, 1000) &&
    hash(s.source_sha256) && hash(s.rendition_sha256) &&
    (s.classification === "public_snapshot" ? s.effective_status === "unknown" && s.effective_from === null && s.effective_until === null
      : s.classification === "synthetic" && s.effective_status === "demo_interval" && date(s.effective_from) &&
        (s.effective_until === null || date(s.effective_until)));
  const supplements = Array.isArray(r?.supplements) && r.supplements.length <= 50 && r.supplements.every((s, i) => s &&
    s.sequence === i + 1 && (s.at === null || date(s.at)) && Array.isArray(s.reasons) && s.reasons.length <= 10 &&
    s.reasons.every(reason => text(reason, 100)) &&
    (s.binding_status === "bound" ? date(s.at) && source(s.source) && (s.source_changed_from_submission === null || typeof s.source_changed_from_submission === "boolean") && s.reasons.length === 0
      : s.binding_status === "unresolved" && s.source === null && s.reasons.length > 0 && s.source_changed_from_submission === null));
  if (!r || r.schema_version !== "unified-workflow.v1" || r.action_authority !== "none" || r.classification !== "synthetic" ||
      r.resource?.id !== id || r.resource.kind !== kind || r.resource.version !== version || !["student", "staff"].includes(r.resource.view) ||
      r.institutional_rules_verified !== false || !supplements ||
      !text(r.definition_version, 100) || typeof r.current_source_differs !== "boolean" ||
      !Array.isArray(r.mandatory_reviews) || r.mandatory_reviews.length < 1 || r.mandatory_reviews.length > 10 ||
      !r.mandatory_reviews.every(c => c && text(c.id, 100) && text(c.label, 300) && c.required === true &&
        c.reviewer === "SUPPORT_OFFICER" && c.status === "required") ||
      (r.binding_status === "bound" ? !r.binding || !r.template ||
        r.readiness !== (r.supplements.some(s => s.binding_status === "unresolved") ? "undetermined" : "requires_officer_review") ||
        r.binding.workflow_version !== r.definition_version || r.binding.template_version !== r.template.version ||
        !text(r.template.title, 200) || !hash(r.binding.sha256) || !text(r.binding.as_of, 64) ||
        !Number.isFinite(Date.parse(r.binding.as_of)) || !source(r.binding.source) ||
        !Array.isArray(r.binding.supporting_sources) || r.binding.supporting_sources.length > 5 ||
        !r.binding.supporting_sources.every(source) || (r.binding.source_capture_at !== null && !date(r.binding.source_capture_at))
        : r.binding_status !== "unresolved" || r.binding !== null || r.template !== null || r.readiness !== "undetermined")) {
    throw new Error("Quy trình hoặc nguồn chưa khớp hồ sơ đang mở. Tải lại hồ sơ để đối chiếu.");
  }
  return r;
}

export function WorkflowDefinitionPanel({ id, version, kind = "service_request" }: { id: string; version: number; kind?: ResourceKind }) {
  const [result, setResult] = useState<WorkflowPackage | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const active = useRef<AbortController | null>(null);
  useEffect(() => {
    active.current?.abort(); active.current = null; setResult(null); setError(""); setPending(false);
    return () => { active.current?.abort(); active.current = null; };
  }, [id, version, kind]);

  async function inspect() {
    active.current?.abort();
    const controller = new AbortController(); active.current = controller;
    setPending(true); setResult(null); setError("");
    const timeout = window.setTimeout(() => controller.abort(), 10000);
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      const response = await fetch(`${base}/v1/assistant/workflows/resolve`, { method: "POST", headers,
        credentials: "include", cache: "no-store", signal: controller.signal,
        body: JSON.stringify({ resource: { kind, id, expected_version: version } }) });
      if (!response.ok) throw new Error(response.status === 409 ? "Hồ sơ hoặc nguồn đã thay đổi. Tải lại để đối chiếu."
        : response.status === 401 ? "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."
        : "Chưa đọc được quy trình trong quyền hiện tại. Bạn vẫn có thể giữ nháp và thao tác thủ công.");
      const value = decode(await response.json(), id, version, kind);
      if (active.current === controller && !controller.signal.aborted) setResult(value);
    } catch (failure) {
      if (active.current === controller) setError(controller.signal.aborted ? "Chưa nhận được quy trình trong thời hạn. Hồ sơ vẫn được giữ."
        : failure instanceof Error ? failure.message : "Quy trình chưa sẵn sàng.");
    } finally {
      window.clearTimeout(timeout);
      if (active.current === controller) { active.current = null; setPending(false); }
    }
  }

  return <section className="mt-4 border-t border-blue-200 pt-4 dark:border-blue-800" aria-label="Quy trình áp dụng">
    <h4 className="font-semibold">Quy trình áp dụng</h4>
    <p className="my-2 text-sm">Đối chiếu nguồn, mẫu và các yêu cầu kiểm tra theo mốc hồ sơ.</p>
    <button type="button" className="fluent-btn-primary" disabled={pending} onClick={() => void inspect()}>{pending ? "Đang đọc quy trình…" : "Xem quy trình áp dụng"}</button>
    {error && <p role="alert" className="mt-3 text-sm text-red-700 dark:text-red-300">{error}</p>}
    {result && <div className="mt-3 space-y-2 text-sm">
      <p role="status">{result.binding_status === "bound" ? "Đã đối chiếu phiên bản áp dụng" : "Chưa đủ nguồn để xác định mẫu hoặc kết luận"}</p>
      <p>Mô phỏng local · Chưa xác minh quy trình và mẫu chính thức HUCE.</p>
      {result.current_source_differs && <p>Nguồn hiện tại khác nguồn trong hồ sơ. Cần đối chiếu; không tự thay phiên bản đã dùng.</p>}
      {result.binding && result.template && <div className="break-words">
        <p>Mẫu mô phỏng: {result.template.title} · {result.template.version}</p>
        <p>Mốc áp dụng: {new Date(result.binding.as_of).toLocaleString("vi-VN", { timeZone: "Asia/Bangkok" })}</p>
        <details><summary>Nguồn và phiên bản đã dùng</summary>
          {[result.binding.source, ...result.binding.supporting_sources].map(s => <div key={`${s.version_id}:${s.locator}`}>
            <p>{s.classification === "public_snapshot" ? "Bản chụp công khai" : "Nguồn mô phỏng"}: {s.locator}</p>
            <p>Phiên bản nguồn: {s.version_id}</p>
            <p>{s.effective_status === "unknown" ? "Chưa xác minh ngày hiệu lực chính thức của nguồn." : "Khoảng hiệu lực cấu hình cho dữ liệu mô phỏng."}</p>
            <p className="break-all">SHA256 bản gốc: {s.source_sha256}</p>
            <p className="break-all">SHA256 nội dung: {s.rendition_sha256}</p>
          </div>)}
          <p className="break-all">Binding: {result.binding.sha256}</p>
        </details>
      </div>}
      {result.supplements.length > 0 && <div><p className="font-medium">Nguồn của các lượt bổ sung</p>
        <ol className="list-inside list-decimal space-y-2">{result.supplements.map(s => <li key={s.sequence}>
          {s.at ? new Date(s.at).toLocaleString("vi-VN", { timeZone: "Asia/Bangkok" }) : "Chưa ghi nhận thời điểm"} · {s.binding_status === "bound"
            ? s.source_changed_from_submission === null ? "Chưa đối chiếu với nguồn lần gửi ban đầu" : s.source_changed_from_submission ? "Nguồn khác lần gửi ban đầu" : "Cùng nguồn lần gửi ban đầu"
            : "Chưa đối chiếu được nguồn bổ sung"}
          {s.source && <p className="break-words">{s.source.locator} · {s.source.version_id}</p>}
        </li>)}</ol>
        {result.supplements.some(s => s.binding_status === "unresolved") && <p>Chưa đủ lịch sử nguồn bổ sung để kết luận khả năng xử lý.</p>}
      </div>}
      <p className="font-medium">Yêu cầu kiểm tra của quy trình</p>
      <ul className="list-inside list-disc space-y-1">{result.mandatory_reviews.map(c => <li key={c.id}>{c.label} · Bắt buộc</li>)}</ul>
      <p>Thông tin này chưa chứng minh đã hoàn thành kiểm tra và không cấp quyền gửi hoặc phê duyệt.</p>
    </div>}
  </section>;
}
