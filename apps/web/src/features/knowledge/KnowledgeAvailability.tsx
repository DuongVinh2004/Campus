"use client";
import React, { useEffect, useState } from "react";

export function KnowledgeAvailability() {
  const [status, setStatus] = useState<{ ready: boolean; message: string; serving_documents: number; pending_versions: number;
    total_sources?: number; unserved_sources?: number; historical_pending_versions?: number;
    equivalent_sources?: number; unresolved_sources?: number; actionable_pending_versions?: number;
    limited_sources?: number; scope_unresolved_sources?: number } | null>(null);
  const [signedIn, setSignedIn] = useState(false);
  useEffect(() => {
    let active = true;
    fetch("/v1/users/me", { cache: "no-store", credentials: "include" })
      .then(response => { if (active) setSignedIn(response.ok); }).catch(() => { if (active) setSignedIn(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    let active = true;
    const update = async () => {
      try {
        const response = await fetch("/v1/knowledge/platform/availability", { cache: "no-store" });
        if (!response.ok) throw new Error("Unavailable");
        const value = await response.json();
        if (active) setStatus(value);
      } catch { if (active) setStatus(null); }
    };
    void update(); const timer = setInterval(() => void update(), 5000);
    return () => { active = false; clearInterval(timer); };
  }, []);
  const headline = status?.message || "Chưa xác nhận được trạng thái kho HUCE. Không coi chatbot là đã có nguồn sẵn sàng.";
  return <aside role="status" className="knowledge-availability" data-ready={status ? "true" : "false"}>
    <div className="knowledge-availability-line">
      <span className="knowledge-availability-dot" aria-hidden="true" />
      <p className="knowledge-availability-headline">{headline}</p>
      {!signedIn && <a href="/login" className="knowledge-availability-link">Đăng nhập</a>}
    </div>
    <details className="knowledge-availability-details">
      <summary>Chi tiết kho nguồn</summary>
      {status && <p>{status.serving_documents} tài liệu đang phục vụ
        {status.total_sources !== undefined && status.unserved_sources !== undefined
          ? status.equivalent_sources !== undefined && status.unresolved_sources !== undefined
            ? ` / ${status.total_sources} nguồn · ${status.equivalent_sources} nguồn trùng/liên kết được bao phủ · ${status.unresolved_sources} nguồn chưa được bao phủ.`
            : ` / ${status.total_sources} nguồn · ${status.unserved_sources} nguồn chưa phục vụ.`
          : ` · ${status.pending_versions} phiên bản chờ duyệt.`}</p>}
      {status?.historical_pending_versions !== undefined && <p>
        {status.pending_versions} phiên bản chưa duyệt, gồm {status.historical_pending_versions} bản lịch sử của nguồn đã có phiên bản trong release.
        Một nguồn có thể có nhiều phiên bản; số phiên bản chưa duyệt không phải số tài liệu chưa phục vụ.
        {status.actionable_pending_versions !== undefined && ` Còn ${status.actionable_pending_versions} phiên bản cần xử lý ngoài phần lịch sử/trùng liên kết.`}
      </p>}
      {!!status?.limited_sources && <p>{status.limited_sources} nguồn đang có giới hạn phần chữ/bảng/sơ đồ đã xác minh;
        trong đó {status.scope_unresolved_sources || 0} nguồn chưa đủ căn cứ gán khóa. Đã lập chỉ mục không đồng nghĩa đã đọc đầy đủ mọi hình và điều kiện.</p>}
      <p>Chưa kết nối tài khoản sinh viên/SSO HUCE. <a href="/knowledge/sources" className="underline">Quản trị nguồn</a></p>
    </details>
  </aside>;
}
