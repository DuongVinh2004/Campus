"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { AppShell } from "../../components/AppShell";
import { KnowledgeReview, type KnowledgeDocItem } from "../../features/knowledge/KnowledgeReview";
import { AsyncState, type AsyncStatus } from "../../components/AsyncState";
import { Search, BookOpen, RefreshCw, ArrowRight } from "lucide-react";
import { ApiClient } from "../../lib/api/client";

const API_BASE_URL = CAMPUS_API_BASE_URL;
interface KnowledgeSourceItem { id: string; source_type: string; canonical_uri: string; title: string; owner_unit: string; authority_level: number; approval_status: string; version: number; has_serving_version?: boolean; }

export default function KnowledgePage() {
  const [items, setItems] = useState<KnowledgeSourceItem[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [status, setStatus] = useState<AsyncStatus>("loading");
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const load = useCallback(async () => {
    setStatus("loading"); setError("");
    try { const result = await new ApiClient({ baseUrl: API_BASE_URL }).get<{ items: KnowledgeSourceItem[] }>("/v1/knowledge/sources"); setItems(result.items || []); setStatus("success"); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Không thể đọc nguồn tri thức. Kiểm tra phiên và thử lại."); setStatus("error"); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const visible = items.filter(item => (filter === "all" || (filter === "approved" ? item.approval_status.toLowerCase() === "approved" : item.approval_status.toLowerCase() !== "approved")) && `${item.title} ${item.owner_unit}`.toLocaleLowerCase("vi").includes(query.toLocaleLowerCase("vi")));
  const source = items.find(item => item.id === selected);
  const doc: KnowledgeDocItem | null = source ? { id: source.id, documentRef: source.id, title: source.title, status: source.has_serving_version ? "published" : "pending_review", authorId: "", department: source.owner_unit, version: String(source.version), sourceUri: source.canonical_uri, reviewEvidenceComplete: false } : null;
  return <AppShell activeNav="knowledge" userRole="admin"><div className="campus-knowledge space-y-6">
    <header className="campus-page-heading"><div><h1>Quản trị tri thức & quy chế học vụ</h1><p>Quản lý nguồn, kiểm duyệt và theo dõi phiên bản văn bản phục vụ trợ lý học vụ.</p></div><nav className="flex flex-wrap gap-2"><Link href="/knowledge/sources" className="fluent-btn-primary">Vận hành nguồn<ArrowRight size={16} /></Link><Link href="/knowledge/policy-graph" className="fluent-btn-secondary">Đồ thị quy chế</Link></nav></header>
    <section className="campus-catalog-intro campus-knowledge-intro"><BookOpen size={28} /><div><h2>Kho tri thức học vụ HUCE</h2><p>Đối chiếu văn bản gốc và trạng thái kiểm duyệt trước khi sử dụng.</p></div><strong>{status === "success" ? items.length : "—"}<small>nguồn đã đọc</small></strong></section>
    <div className="campus-catalog-tools"><label className="campus-catalog-search"><Search size={18} /><input aria-label="Tìm văn bản tri thức" placeholder="Tìm tên văn bản, đơn vị ban hành…" value={query} onChange={event => setQuery(event.target.value)} /></label><button type="button" className="fluent-btn-secondary" disabled={status === "loading"} onClick={() => void load()}><RefreshCw size={16} />Làm mới</button></div>
    <div className="campus-filter-chips" role="group" aria-label="Trạng thái văn bản">{[["all", "Tất cả"], ["approved", "Đã phê duyệt"], ["pending", "Chờ kiểm duyệt"]].map(([value, label]) => <button key={value} type="button" aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}</div>
    <AsyncState status={status} errorMessage={error} onRetry={() => void load()} loadingMessage="Đang đọc nguồn tri thức…">
      {!visible.length ? <div className="campus-empty-state" role="status"><BookOpen size={28} /><h2>Chưa có văn bản phù hợp</h2><p>Nguồn được cấp quyền sẽ xuất hiện tại đây sau khi đọc thành công.</p></div> : <div className="campus-knowledge-list">{visible.map(item => <article key={item.id}><span className="campus-catalog-icon"><BookOpen size={22} /></span><div><h2>{item.title}</h2><p>{item.owner_unit} · Phiên bản {item.version}</p><small>{item.approval_status}</small></div><button type="button" className="fluent-btn-secondary" aria-expanded={selected === item.id} onClick={() => setSelected(selected === item.id ? null : item.id)}>Xem văn bản</button></article>)}</div>}
      {doc && <section className="space-y-4"><p className="campus-save-state">Danh mục chưa cung cấp đủ bằng chứng thẩm định. Mở Vận hành nguồn hoặc Đồ thị quy chế để thực hiện quy trình có kiểm quyền và xác nhận.</p><KnowledgeReview document={doc} currentUserId="" userRole="ADMIN" /></section>}
    </AsyncState>
  </div></AppShell>;
}
