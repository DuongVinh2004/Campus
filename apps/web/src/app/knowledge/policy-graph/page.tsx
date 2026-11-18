"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";

import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "../../../components/AppShell";
import { ApiClient } from "../../../lib/api/client";
import { PolicyGraphReview, type GraphView } from "../../../features/knowledge/PolicyGraphReview";

const baseUrl = CAMPUS_API_BASE_URL;

export default function PolicyGraphPage() {
  const [view, setView] = useState<GraphView | null>(null);
  const [error, setError] = useState("");
  const [ids, setIds] = useState<string[]>([]);
  const load = useCallback(async (id?: string) => {
    setError("");
    try {
      const client = new ApiClient({ baseUrl });
      const list = await client.get<{ items: { id: string }[] }>("/v1/policy-graph/versions");
      setIds(list.items.map(i => i.id));
      const chosen = id || list.items[0]?.id;
      setView(chosen ? await client.get<GraphView>(`/v1/policy-graph/versions/${encodeURIComponent(chosen)}`) : null);
    } catch (caught) {
      setView(null);
      setError((caught as { status?: number }).status === 404
        ? "Đồ thị quy chế chưa được bật trong bản chạy này, nên chưa có phiên bản nào để duyệt."
        : "Chưa đọc được graph. Cần đăng nhập bằng tài khoản quản trị tri thức có quyền nguồn; kiểm tra dịch vụ rồi thử lại.");
    }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const path = view ? `/v1/policy-graph/versions/${encodeURIComponent(view.proposal.id)}` : "";
  return (
    <AppShell activeNav="knowledge" userRole="admin">
      <div className="campus-knowledge space-y-5">
        <header className="campus-page-heading">
          <div>
            <h1>Đồ thị quy chế học vụ</h1>
            <p>Đối chiếu nguồn, thẩm định và xuất bản phiên bản tri thức.</p>
          </div>
        </header>
        <div className="campus-panel mb-5 flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <a href="/knowledge" className="fluent-btn-secondary text-sm">
              ← Kho tri thức
            </a>
            {ids.length > 0 && (
              <label className="flex items-center gap-2 text-sm font-medium text-[var(--text-primary)]">
                <span>Phiên bản</span>
                <select
                  className="fluent-input w-auto min-w-[160px] text-sm"
                  value={view?.proposal.id || ""}
                  onChange={(e) => void load(e.target.value)}
                >
                  {ids.map((id) => (
                    <option key={id}>{id}</option>
                  ))}
                </select>
              </label>
            )}
          </div>
          <button
            type="button"
            className="fluent-btn-secondary text-sm"
            onClick={() => void load(view?.proposal.id)}
          >
            Tải lại
          </button>
        </div>
        {error && (
          <div
            role="alert"
            className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300"
          >
            {error}
          </div>
        )}
        {!view && !error && (
          <div className="fluent-card border border-[var(--border-color)] bg-[var(--surface-card)] p-5 text-sm text-[var(--text-secondary)]">
            Đang đọc các phiên bản có quyền truy cập, hoặc chưa có graph để review.
          </div>
        )}
        {view && (
          <PolicyGraphReview
            key={view.proposal.id}
            view={view}
            onExtract={async (target) => {
              const result = await new ApiClient({ baseUrl }).post<{ candidate_id: string }>(
                `${path}:extract-candidate`,
                { target_ids: [target] }
              );
              await load(result.candidate_id);
            }}
            onReview={async (target, verdict, note, revision) => {
              await new ApiClient({ baseUrl }).post(`${path}/reviews`, {
                target,
                verdict,
                note,
                expected_revision: revision,
              });
              await load(view.proposal.id);
            }}
            onPreview={async (revision) =>
              new ApiClient({ baseUrl }).post(`${path}:publish-preview`, {
                expected_revision: revision,
              })
            }
            onPublish={async (revision, confirmation) => {
              await new ApiClient({ baseUrl }).post(`${path}:publish`, {
                expected_revision: revision,
                confirmation,
                confirmed: true,
              });
              await load(view.proposal.id);
            }}
          />
        )}
      </div>
    </AppShell>
  );
}
