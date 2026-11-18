"use client";

import React, { FormEvent, useRef, useState } from "react";
import { ApiClient } from "../../lib/api/client";

const base = "/v1/knowledge/platform";
type Axis = { kind: "UNKNOWN" | "ALL" | "VALUES"; values: string[] };
type Witness = { artifact_id: string; artifact_sha256: string; locator: Record<string, unknown>; verbatim: string; text_sha256: string };
type Interval = { from_day: string | null; until_day: string | null; end_kind: "UNKNOWN" | "OPEN" | "KNOWN"; timezone: string; basis: Witness | null };
type Identity = { tenant_id: string; family_id: string; issuer: string; document_number: string | null; issued_on: string | null;
  verification: "CANDIDATE" | "VERIFIED"; identity_basis: Witness | null; effective: Interval;
  scope: Record<"programmes" | "cohorts" | "academic_years", Axis> };
type Relation = { from_edition: string; to_edition: string; kind: string; effective: Interval; witness: Witness; target_unit_ids: string[] };
type Workspace = { state: string; edition_id: string; source_id: string; identity: Identity; expected_revision: number; can_verify: boolean;
  basis_note?: string | null; recorded_at?: string;
  total_pages: number; page: { page_index: number; page: number | null; text: string } | null; page_witness: Witness | null;
  related_editions: Array<{ id: string; created_by: string; recorded_at: string }>;
  relations: Array<{ relation_id: string; revision: number; decision_state: string; created_by: string; relation: Relation; basis_note: string }> };
type Resolution = { state: string; segments: Array<{ scope: Record<string, string | null>;
  selected: Array<{ edition_id: string; unit_ids: string[] }>; excluded: Array<{ edition_id: string; reason: string }>;
  issues: Array<{ reason: string; fields?: string[]; edition_id?: string; edition_ids?: string[] }> }> };
const axes = { programmes: "Chương trình", cohorts: "Khóa", academic_years: "Năm học" } as const;
const names: Record<string, string> = {
  EFFECTIVE_START_UNKNOWN: "Chưa rõ ngày bắt đầu", EFFECTIVE_END_UNKNOWN: "Chưa rõ ngày kết thúc",
  FUTURE_EDITION: "Chưa tới ngày áp dụng", EXPIRED_FOR_QUERY: "Đã hết hiệu lực tại ngày hỏi", OUTSIDE_SCOPE: "Ngoài phạm vi hỏi",
  SCOPE_NEEDS_INFORMATION: "Cần bổ sung phạm vi", IDENTITY_UNVERIFIED: "Định danh chưa được xác minh", EDITION_CONFLICT: "Các bản còn mâu thuẫn",
  FAMILY_CONCLUSION_BLOCKED: "Chưa đủ căn cứ kết luận cho nhóm văn bản", EXPLICIT_REPLACEMENT: "Có căn cứ thay thế",
  DEPENDENCY_GRAPH_UNVERIFIED: "Phụ thuộc điều kiện chưa được xác minh", RELATION_UNVERIFIED: "Quan hệ chưa được xác minh",
  CURRENT_AUTHORIZATION_DENIED: "Quyền sử dụng hiện tại không cho phép", NOT_KNOWN_AT_QUERY_TIME: "Hệ thống chưa biết bản này tại thời điểm hỏi",
};

export function EditionWorkspace({ versionId, actorId }: { versionId: string; actorId: string }) {
  const [open, setOpen] = useState(false);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [draft, setDraft] = useState<Identity | null>(null);
  const [expected, setExpected] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [note, setNote] = useState("");
  const [resolution, setResolution] = useState<Resolution | null>(null);
  const [queryDay, setQueryDay] = useState("");
  const [queryScope, setQueryScope] = useState({ programmes: "", cohorts: "", academic_years: "" });
  const key = useRef<string | null>(null);
  async function load(page = 0, reset = true) {
    const data = await new ApiClient().get<Workspace>(`${base}/versions/${versionId}/edition-workspace?page_index=${page}`);
    setWorkspace(old => reset || !old ? data : { ...old, page: data.page, page_witness: data.page_witness, total_pages: data.total_pages });
    if (reset) { setDraft(data.identity ?? null); setExpected(data.expected_revision ?? 0); setResolution(null); key.current = null; }
  }
  async function run(action: () => Promise<void>) {
    setBusy(true); setError("");
    try { await action(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function post(path: string, body: unknown) {
    key.current ||= crypto.randomUUID();
    const result = await new ApiClient().post(path, body, { "Idempotency-Key": key.current });
    key.current = null; return result;
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!workspace || !draft) return;
    const data = new FormData(event.currentTarget);
    await run(async () => {
      await post(`${base}/editions/${workspace.edition_id}/decisions`, { expected_revision: expected, identity: draft,
        basis_note: note, confirmed_source_basis: data.get("compared") === "on" });
      setNotice("Đã lưu quyết định có lịch sử. Chưa cấp quyền phát hành hoặc đổi bản đang sử dụng."); await load();
    });
  }
  async function relation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!workspace || !draft || !workspace.page_witness) return;
    const data = new FormData(event.currentTarget);
    await run(async () => {
      await post(`${base}/edition-relations/decisions`, { expected_revision: 0, from_edition: workspace.edition_id,
        to_edition: data.get("target"), kind: data.get("kind"), effective: draft.effective, witness: workspace.page_witness,
        basis_note: data.get("note"), decision_state: "PROPOSED", confirmed_source_basis: false });
      setNotice("Đã lưu đề xuất quan hệ; cần người khác đối chiếu căn cứ."); await load();
    });
  }
  if (!open) return <button onClick={() => { setOpen(true); void run(() => load()); }}>Đối chiếu định danh và quan hệ phiên bản</button>;
  return <section aria-label="Quyết định phiên bản có căn cứ" className="rounded-xl border p-3 space-y-3">
    <h3 className="font-semibold">Định danh, phạm vi và hiệu lực</h3>
    <p className="text-sm">Giữ “Chưa rõ” khi nguồn chưa có căn cứ. Quyết định metadata và quan hệ còn tách biệt với duyệt nội dung, phát hành và xác nhận đang sử dụng.</p>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {workspace?.state === "UNMAPPED" && <p>Nguồn cũ chưa được ánh xạ edition. Không suy phiên bản mới nhất từ ngày upload.</p>}
    {workspace?.page && <div className="space-y-2">
      <label>Trang/khối chứa căn cứ<select disabled={busy} value={workspace.page.page_index} onChange={event => void run(() => load(Number(event.target.value), false))}>
        {Array.from({ length: workspace.total_pages }, (_, index) => <option key={index} value={index}>{index + 1}</option>)}</select></label>
      <pre className="whitespace-pre-wrap max-h-64 overflow-auto text-sm border p-2">{workspace.page.text || "Trang không có chữ native đã gắn hash."}</pre>
      <div className="flex flex-wrap gap-3">
        <button disabled={busy || !workspace.page_witness || !draft} onClick={() => { if (draft) { setDraft({ ...draft, identity_basis: workspace.page_witness }); key.current = null; } }}>Dùng trang này làm căn cứ định danh</button>
        <button disabled={busy || !workspace.page_witness || !draft?.effective.from_day} onClick={() => { if (draft) { setDraft({ ...draft, effective: { ...draft.effective, basis: workspace.page_witness } }); key.current = null; } }}>Dùng trang này làm căn cứ hiệu lực</button>
      </div>
    </div>}
    {draft && workspace && <>
      {workspace.expected_revision > 0 && <p className="text-sm">Quyết định đã lưu lần {workspace.expected_revision}{workspace.recorded_at ? ` · ${new Date(workspace.recorded_at).toLocaleString("vi-VN")}` : ""}: {workspace.basis_note}</p>}
      {draft.identity_basis && <details><summary>Căn cứ định danh đang gắn với quyết định</summary><pre className="whitespace-pre-wrap text-sm max-h-48 overflow-auto">{draft.identity_basis.verbatim}</pre></details>}
      {draft.effective.basis && <details><summary>Căn cứ hiệu lực đang gắn với quyết định</summary><pre className="whitespace-pre-wrap text-sm max-h-48 overflow-auto">{draft.effective.basis.verbatim}</pre></details>}
      <form onSubmit={event => void save(event)} onChange={() => { key.current = null; }}>
        <fieldset disabled={busy} className="space-y-3">
          <label className="block">Nhà ban hành<input className="fluent-input w-full" required minLength={2} value={draft.issuer} onChange={event => setDraft({ ...draft, issuer: event.target.value })} /></label>
          <label className="block">Số văn bản nếu có<input className="fluent-input w-full" value={draft.document_number ?? ""} onChange={event => setDraft({ ...draft, document_number: event.target.value || null })} /></label>
          <label className="block">Ngày ban hành nếu nguồn ghi<input type="date" value={draft.issued_on ?? ""} onChange={event => setDraft({ ...draft, issued_on: event.target.value || null })} /></label>
          {Object.entries(axes).map(([name, label]) => { const axis = name as keyof Identity["scope"]; const value = draft.scope[axis]; return <div key={axis}>
            <label>{label}: mức xác định<select value={value.kind} onChange={event => setDraft({ ...draft, scope: { ...draft.scope, [axis]: { kind: event.target.value, values: [] } } })}>
              <option value="UNKNOWN">Chưa rõ</option><option value="ALL">Tất cả — cần căn cứ</option><option value="VALUES">Các giá trị cụ thể</option></select></label>
            {value.kind === "VALUES" && <label>{label}: giá trị cách nhau bằng dấu phẩy<input required value={value.values.join(",")} onChange={event => setDraft({ ...draft, scope: { ...draft.scope, [axis]: { ...value, values: event.target.value.split(",").map(v => v.trim()) } } })} /></label>}
          </div>; })}
          <label className="block">Ngày bắt đầu áp dụng<input type="date" value={draft.effective.from_day ?? ""} onChange={event => setDraft({ ...draft, effective: { ...draft.effective, from_day: event.target.value || null, basis: null, until_day: null, end_kind: "UNKNOWN" } })} /></label>
          <label className="block">Kết thúc áp dụng<select value={draft.effective.end_kind} onChange={event => setDraft({ ...draft, effective: { ...draft.effective, end_kind: event.target.value as Interval["end_kind"], until_day: null } })}>
            <option value="UNKNOWN">Chưa rõ</option><option value="OPEN" disabled={!draft.effective.from_day}>Không ấn định ngày kết thúc — có căn cứ</option><option value="KNOWN" disabled={!draft.effective.from_day}>Có ngày kết thúc cụ thể</option></select></label>
          {draft.effective.end_kind === "KNOWN" && <label>Ngày kết thúc (không bao gồm ngày này)<input required type="date" value={draft.effective.until_day ?? ""} onChange={event => setDraft({ ...draft, effective: { ...draft.effective, until_day: event.target.value || null } })} /></label>}
          <p className="text-sm">Căn cứ định danh: {draft.identity_basis ? "đã chọn đoạn gắn hash" : "chưa chọn"}. Căn cứ hiệu lực: {draft.effective.basis ? "đã chọn đoạn gắn hash" : "chưa chọn"}.</p>
          <label className="block">Mức đối chiếu<select value={draft.verification} onChange={event => setDraft({ ...draft, verification: event.target.value as Identity["verification"] })}>
            <option value="CANDIDATE">Đề xuất, chưa xác minh</option><option value="VERIFIED" disabled={!workspace.can_verify}>Đã đối chiếu độc lập</option></select></label>
          {!workspace.can_verify && <p>Người tạo hồ sơ hoặc quyết định trước cần người khác đối chiếu độc lập.</p>}
          <label className="block">Căn cứ quyết định<textarea required minLength={10} maxLength={2000} className="fluent-input w-full" value={note} onChange={event => setNote(event.target.value)} /></label>
          <label className="block"><input type="checkbox" name="compared" required={draft.verification === "VERIFIED"} /> Tôi đã đối chiếu nguồn, các ngày và phạm vi được khai.</label>
          <button type="submit" disabled={draft.verification === "VERIFIED" && !workspace.can_verify}>Lưu quyết định phiên bản</button>
        </fieldset>
      </form>
      <details className="border-t pt-3"><summary>Quan hệ với edition khác của cùng nguồn</summary>
        <form onSubmit={event => void relation(event)} onChange={() => { key.current = null; }}><fieldset disabled={busy} className="space-y-3 mt-3">
          <label className="block">Edition được tác động<select name="target" required><option value="">Chọn bản để đối chiếu</option>{workspace.related_editions.filter(item => item.id !== workspace.edition_id).map(item => <option key={item.id} value={item.id}>{item.id} · ghi nhận {item.recorded_at}</option>)}</select></label>
          <label className="block">Loại quan hệ<select name="kind"><option value="REPLACES">Thay thế toàn bộ</option><option value="SUPPLEMENTS">Bổ sung, giữ cả hai</option><option value="ALIAS">Cùng văn bản qua nguồn tương đương</option></select></label>
          <p className="text-sm">Căn cứ là trang đang mở và khoảng hiệu lực đã khai phía trên. Sửa một phần cần bản đồ đơn vị và phụ thuộc đã xác minh.</p>
          <label className="block">Căn cứ đề xuất quan hệ<textarea name="note" required minLength={10} maxLength={2000} className="fluent-input w-full" /></label>
          <button disabled={!workspace.page_witness} type="submit">Lưu đề xuất quan hệ</button>
        </fieldset></form>
        {workspace.relations.map(item => <form key={item.relation_id} className="mt-3 border-t p-2" onChange={() => { key.current = null; }} onSubmit={event => {
          event.preventDefault(); const data = new FormData(event.currentTarget);
          void run(async () => { const { from_edition, to_edition, kind, effective, witness, target_unit_ids } = item.relation;
            await post(`${base}/edition-relations/decisions`, { relation_id: item.relation_id, expected_revision: item.revision,
              from_edition, to_edition, kind, effective, witness, target_unit_ids, decision_state: data.get("verdict"), basis_note: data.get("note"), confirmed_source_basis: data.get("compared") === "on" });
            setNotice("Đã ghi quyết định quan hệ mới, giữ các quyết định cũ."); await load(); });
        }}><p className="text-sm">{item.relation.kind} · {item.decision_state} · lần {item.revision}: {item.basis_note}</p>
          <pre className="whitespace-pre-wrap text-sm max-h-40 overflow-auto">{item.relation.witness.verbatim}</pre>
          {item.created_by === actorId || workspace.related_editions.some(edition => [item.relation.from_edition, item.relation.to_edition].includes(edition.id) && edition.created_by === actorId)
            ? <p>Cần người khác có quyền đối chiếu quan hệ này.</p>
            : <fieldset disabled={busy} className="space-y-2"><label className="block">Kết luận quan hệ<select name="verdict"><option value="REJECTED">Từ chối</option><option value="VERIFIED">Đã xác minh độc lập</option></select></label>
              <label className="block">Ghi nhận đối chiếu quan hệ<textarea name="note" required minLength={10} maxLength={2000} className="fluent-input w-full" /></label>
              <label className="block"><input type="checkbox" name="compared" required /> Tôi đã mở đúng nguồn và đối chiếu căn cứ quan hệ.</label><button type="submit">Ghi quyết định quan hệ độc lập</button></fieldset>}
        </form>)}
      </details>
      <form className="border-t pt-3 space-y-3" onSubmit={event => { event.preventDefault(); void run(async () => {
        const scope = Object.fromEntries(Object.entries(queryScope).map(([name, value]) => [name, value ? value.split(",").map(v => v.trim()) : []]));
        setResolution(await new ApiClient().post<Resolution>(`${base}/resolve-preview`, { family_ids: [workspace.source_id], at_day: queryDay, ...scope }));
      }); }}><h4 className="font-semibold">Xem lý do chọn phiên bản</h4>
        <label>Ngày áp dụng cần hỏi<input type="date" required value={queryDay} onChange={event => setQueryDay(event.target.value)} /></label>
        {Object.entries(axes).map(([name, label]) => <label key={name} className="block">{label} cần hỏi (để trống khi chưa biết)<input value={queryScope[name as keyof typeof queryScope]} onChange={event => setQueryScope({ ...queryScope, [name]: event.target.value })} /></label>)}
        <button disabled={busy} type="submit">Đối chiếu lựa chọn theo ngày và phạm vi</button>
      </form>
      {resolution && <div aria-label="Lý do lựa chọn phiên bản" className="space-y-2"><p>{resolution.state === "RESOLVED" ? "Đã xác định bản phù hợp trong bước xem trước" : resolution.state === "NEEDS_INFORMATION" ? "Cần thêm thông tin hoặc xác minh" : "Chưa có bản áp dụng"}</p>
        {resolution.segments.map((segment, index) => <div key={index} className="text-sm border p-2">
          <p>{Object.entries(segment.scope).map(([name, value]) => `${axes[name as keyof typeof axes]}: ${value ?? "chưa khai"}`).join(" · ")}</p>
          {segment.selected.map(item => <p key={item.edition_id}>Bản được chọn: {item.edition_id}</p>)}
          {[...segment.issues, ...segment.excluded].map((item, i) => <p key={i}>{names[item.reason] ?? item.reason}{"fields" in item && item.fields?.length ? `: ${item.fields.join(", ")}` : ""}</p>)}
        </div>)}<p className="text-sm">Kết quả xem trước chưa xác nhận phát hành hoặc runtime đang sử dụng.</p></div>}
    </>}
    <div className="flex gap-3"><button disabled={busy} onClick={() => void run(() => load())}>Tải quyết định hiện tại</button><button onClick={() => setOpen(false)}>Đóng đối chiếu phiên bản</button></div>
  </section>;
}
