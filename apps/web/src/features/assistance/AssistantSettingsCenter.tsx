"use client";

import { useEffect, useState, type ReactNode } from "react";
import { Settings2 } from "lucide-react";
import Link from "next/link";
import { useUnifiedAssistant } from "@/lib/unified-assistant-runtime";
import { assistantClientId, type AssistantPreferences, type ActorStatePreview, type AssistantGrant, type ConsentState, type GrantSpec } from "@/lib/assistant-state-service";
import { AccessibleDialog } from "@/components/shared/AccessibleDialog";
import { AssistantContent } from "@/features/chat/ChatPanel";

const defaults: AssistantPreferences = { locale: "vi", reply_style: "concise", verbosity: "normal", format: "markdown", display_name: "", address_as: "", custom_instructions: "" };
type Pending = { kind: "preferences" | "grants"; preview: ActorStatePreview; clientId: string; label: string; settings?: boolean };
const purposes: Record<ConsentState["purpose"], string> = { OPTIONAL_PERSONALIZATION: "Cá nhân hóa cách trả lời", CONVERSATION_HISTORY: "Dùng tối đa 5 lượt cùng hội thoại", QUALITY_FEEDBACK: "Ghi lựa chọn về phản hồi chất lượng; chưa bật training" };

function SettingsSurface({ inline, ...props }: { inline: boolean } & Parameters<typeof AccessibleDialog>[0]) {
  return inline ? <section aria-labelledby={props.labelledBy} className="campus-settings-surface">{props.children}</section> : <AccessibleDialog {...props} />;
}

export function AssistantSettingsCenter({ inline = false, compact = false, iconOnly = false, controlledOpen, onClose, navigation }: { inline?: boolean; compact?: boolean; iconOnly?: boolean; controlledOpen?: boolean; onClose?: () => void; navigation?: ReactNode }) {
  const runtime = useUnifiedAssistant(), { service, capabilities, active } = runtime;
  const [scope, setScope] = useState<"account" | "chat">("account");
  const [values, setValues] = useState<AssistantPreferences>(defaults);
  const [version, setVersion] = useState<number | null>(null);
  const [override, setOverride] = useState(true);
  const [consents, setConsents] = useState<ConsentState[]>([]);
  const [notice, setNotice] = useState<{ version: string; status: string; disclaimer: { statement: string } } | null>(null);
  const [grants, setGrants] = useState<AssistantGrant[]>([]);
  const [grantCursor, setGrantCursor] = useState<string | null>(null);
  const [capability, setCapability] = useState<GrantSpec["capability"]>("read_source");
  const [lifetime, setLifetime] = useState<GrantSpec["lifetime"]>("once");
  const [pending, setPending] = useState<Pending | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [dirty, setDirty] = useState(false);
  const [localOpen, setLocalOpen] = useState(inline);
  const open = controlledOpen ?? localOpen;
  const setOpen = (value: boolean) => { setLocalOpen(value); if (!value) onClose?.(); };
  const [uses, setUses] = useState<Record<string, string>>({});
  const [projection, setProjection] = useState<{ text: string; receipt: string } | null>(null);

  useEffect(() => {
    if (!open || !runtime.actor) return;
    let live = true; setVersion(null); setError("");
    async function read() {
      try {
        await runtime.guard();
        const results = await Promise.allSettled([
          scope === "account" ? service.readPreferences() : active?.id ? service.chatPreferences(active.id) : Promise.reject(new Error("Cần hội thoại đã lưu để tạo override")),
          service.consentNotice(), service.consentState(), capabilities?.grants ? service.grants() : Promise.resolve({ items: [] as AssistantGrant[], page: { next_cursor: null } }),
        ]);
        await runtime.guard(); if (!live) return;
        const [settings, currentNotice, states, currentGrants] = results;
        if (settings.status === "fulfilled") {
          const data = settings.value;
          setVersion(data.version);
          if (!dirty) { setValues("preferences" in data ? data.preferences : data.override?.preferences || data.effective); setOverride("override" in data ? data.override?.enabled ?? true : true); }
        }
        if (currentNotice.status === "fulfilled") setNotice(currentNotice.value);
        if (states.status === "fulfilled") setConsents(states.value.items);
        if (currentGrants.status === "fulfilled") { setGrants(currentGrants.value.items); setGrantCursor(currentGrants.value.page.next_cursor); }
        const failures = results.filter((result): result is PromiseRejectedResult => result.status === "rejected");
        if (failures.length) setError(failures.map(result => result.reason instanceof Error ? result.reason.message : "Chưa đọc được một phần settings").join(" · "));
      } catch (failure) { if (live) setError(failure instanceof Error ? failure.message : "Chưa đọc được settings."); }
    }
    void read(); return () => { live = false; };
  }, [open, scope, active?.id, runtime.actor?.user_id]);

  async function run(action: () => Promise<void>) {
    if (busy) return; setBusy(true); setError(""); setMessage("");
    try { await runtime.guard(); await action(); await runtime.guard(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Chưa lưu; nội dung đang soạn và preview được giữ."); }
    finally { setBusy(false); }
  }
  async function prepareSettings() {
    if (version === null) return;
    const clientId = assistantClientId();
    const preview = scope === "account" ? await service.previewPreferences(values, version, clientId)
      : active?.id ? await service.previewChatPreferences(active.id, values, version, clientId, override) : null;
    if (preview) { setConfirmed(false); setPending({ kind: "preferences", preview, clientId, settings: true,
      label: `${scope === "account" ? "Settings tài khoản" : override ? "Override hội thoại hiện tại" : "Tắt override hội thoại"}: ${values.locale}, ${values.reply_style}, ${values.verbosity}, ${values.format}. Tên: ${values.display_name || "mặc định"}. Xưng hô: ${values.address_as || "mặc định"}. Chỉ dẫn: ${values.custom_instructions || "không có"}.` }); }
  }
  async function refreshAfterCommit(expectedSettingsVersion?: number) {
    const data = scope === "account" ? await service.readPreferences() : active?.id ? await service.chatPreferences(active.id) : null;
    if (expectedSettingsVersion !== undefined) {
      if (!data || !data.saved || !Number.isSafeInteger(data.version) || data.version < expectedSettingsVersion) {
        throw new Error("Chưa xác nhận được phiên bản cài đặt đã lưu; bản soạn và preview được giữ.");
      }
      setValues("preferences" in data ? data.preferences : data.override?.preferences || data.effective);
      if ("override" in data) setOverride(data.override?.enabled ?? false);
    }
    if (data) setVersion(data.version);
    setConsents((await service.consentState()).items);
    if (capabilities?.grants) { const page = await service.grants(); setGrants(page.items); setGrantCursor(page.page.next_cursor); }
  }
  async function confirm() {
    if (!pending || !confirmed) return;
    const response = await service.confirm(pending.kind, pending.preview, true);
    if (!response.saved || response.receipt.client_id !== pending.clientId || response.receipt.state !== "committed" || pending.settings && (!Number.isSafeInteger(response.receipt.version) || response.receipt.version < 1)) throw new Error("Receipt chưa khớp; cần đọc lại.");
    setMessage(`Đã commit · receipt ${response.receipt.receipt_id}. Đang đọc lại state…`);
    await refreshAfterCommit(pending.settings ? response.receipt.version : undefined); setPending(null); if (pending.settings) setDirty(false); setConfirmed(false);
    setMessage(`Đã lưu và đọc lại · receipt ${response.receipt.receipt_id}`);
  }
  async function consent(value: ConsentState, decision: "GRANTED" | "WITHDRAWN") {
    if (!notice || !notice.version.endsWith(".assistant-features.v1") || notice.status !== "ACTIVE") throw new Error("Notice consumer hiện hành chưa sẵn sàng.");
    const clientId = assistantClientId();
    const preview = await service.previewConsent(value.purpose, decision, notice.version, value.version, clientId);
    setConfirmed(false); setPending({ kind: "preferences", preview, clientId, label: `${decision === "GRANTED" ? "Cho phép" : "Rút consent"}: ${purposes[value.purpose]} theo notice ${notice.version}. ${notice.disclaimer.statement}` });
  }
  async function prepareGrant() {
    if (!runtime.surface.resource) throw new Error("Mở hồ sơ đã lưu để chọn đúng phạm vi và phiên bản quyền.");
    const clientId = assistantClientId();
    const preview = await service.previewGrant({ client_id: clientId, resource: runtime.surface.resource, capability, purpose: "source_assistance", lifetime, lifetime_seconds: lifetime === "timed" ? 600 : 60 });
    setConfirmed(false); setPending({ kind: "grants", preview, clientId, label: `Cho phép ${capability} với ${runtime.surface.resource.kind} ${runtime.surface.resource.id}, phiên bản ${runtime.surface.resource.expected_version}, ${lifetime}. Chỉ đọc/chuẩn bị; nghiệp vụ vẫn yêu cầu xác nhận riêng.` });
  }
  async function revoke(grant: AssistantGrant) {
    const clientId = assistantClientId(), preview = await service.previewRevoke(grant.id, grant.version, clientId);
    setConfirmed(false); setPending({ kind: "grants", preview, clientId, label: `Rút quyền ${grant.capability} cho ${grant.resource.id} tại phiên bản quyền ${grant.version}.` });
  }
  async function readGranted(grant: AssistantGrant) {
    const operation = uses[grant.id] || assistantClientId(); setUses(previous => ({ ...previous, [grant.id]: operation }));
    if (grant.capability === "read_source") {
      const result = await service.composeContext({ resource: grant.resource, grant_id: grant.id, operation_id: operation });
      await runtime.guard();
      if (!result.receipt || result.receipt.client_id !== operation) throw new Error("Chưa xác nhận receipt context");
      const resource = result.content.resource as { guidance?: string } | null;
      setProjection({ text: resource?.guidance || "Projection không có hướng dẫn; authority vẫn là none.", receipt: result.receipt.receipt_id });
    } else if (grant.capability === "read_own_resource") {
      const result = await service.readOwnResource(grant.id, grant.resource, operation);
      await runtime.guard();
      if (result.result.action_authority !== "none" || result.receipt.client_id !== operation) throw new Error("Consumer readback không hợp lệ");
      setProjection({ text: Object.entries(result.result.fields).map(([key, value]) => `${key}: ${String(value)}`).join("\n\n"), receipt: result.receipt.receipt_id });
    } else throw new Error("Chuẩn bị nháp yêu cầu proposal và workflow evidence tại hồ sơ; settings chỉ quản lý quyền.");
    await refreshAfterCommit();
  }
  function edit(patch: Partial<AssistantPreferences>) { setValues(previous => ({ ...previous, ...patch })); setDirty(true); }
  return <>
    {!inline && controlledOpen === undefined && <button type="button" disabled={!capabilities || !runtime.actor} onClick={() => setOpen(true)} aria-label={iconOnly ? "Cài đặt" : undefined} title={iconOnly ? "Cài đặt" : undefined} className={iconOnly ? "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800" : "fluent-btn-secondary"}>{iconOnly ? <Settings2 aria-hidden="true" className="h-4 w-4" /> : compact ? "Cài đặt" : "Cài đặt và quyền trợ lý"}</button>}
    {!capabilities && <p role="status" className="text-sm">{runtime.error || "Chưa xác nhận capability settings cho phiên và vai trò này."}</p>}
    <SettingsSurface inline={inline} open={open} onClose={() => { if (!busy) setOpen(false); }} labelledBy="assistant-settings-title" className="fixed inset-4 max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-xl bg-white p-5 text-slate-900 dark:bg-slate-950 dark:text-slate-100 sm:left-auto sm:w-[min(680px,90vw)]">
      <h2 id="assistant-settings-title" className="text-xl font-semibold">Cài đặt và quyền · {capabilities?.audience === "staff" ? "Cán bộ" : "Sinh viên"}</h2>
      {!inline && <button type="button" disabled={busy} className="fluent-btn-secondary my-3" onClick={() => setOpen(false)}>Đóng</button>}
      {navigation && <fieldset disabled={busy} className="mb-4 border-b pb-4"><legend className="mb-2 text-sm font-semibold">Chung</legend>{navigation}</fieldset>}
      {error && <p role="alert" className="my-3 text-red-700 dark:text-red-300">{error} Nội dung đang soạn được giữ; đọc lại khi có CAS/network lỗi.</p>}
      {message && <p role="status" className="my-3">{message}</p>}
      <p role="status" className="campus-save-state">{busy ? "Đang xử lý…" : error ? "Chưa lưu được · bản soạn được giữ" : dirty ? "Có thay đổi chưa lưu" : version === null ? "Đang đọc cài đặt…" : "Đã đọc cài đặt hiện tại"} · Xem trước và xác nhận để lưu.</p>
      {!capabilities?.model_preferences && <p role="status" className="my-3">Settings trình bày được lưu riêng; writer đang phục vụ chưa tiêu dùng settings này: {capabilities?.locked_reasons.model_preferences || "Chưa xác nhận capability"}.</p>}
      <label className="block my-3">Phạm vi<select className="fluent-input" value={scope} disabled={busy || Boolean(pending)} onChange={e => { setScope(e.target.value as "account" | "chat"); setDirty(false); }}><option value="account">Tài khoản</option><option value="chat" disabled={!active?.id || !capabilities?.chat_preferences}>Hội thoại hiện tại</option></select></label>
      {scope === "chat" && <label className="block"><input type="checkbox" disabled={busy || Boolean(pending)} checked={override} onChange={e => { setOverride(e.target.checked); setDirty(true); }} /> Dùng override trong hội thoại này</label>}
      <fieldset disabled={busy || Boolean(pending)}><div className="grid gap-3 sm:grid-cols-2 my-4">
        <label>Ngôn ngữ<select className="fluent-input" value={values.locale} onChange={e => edit({ locale: e.target.value as "vi" | "en" })}><option value="vi">Tiếng Việt</option><option value="en">English</option></select></label>
        <label>Cách trả lời<select className="fluent-input" value={values.reply_style} onChange={e => edit({ reply_style: e.target.value as AssistantPreferences["reply_style"] })}><option value="concise">Ngắn gọn</option><option value="steps">Từng bước</option><option value="detailed">Chi tiết</option></select></label>
        <label>Độ dài<select className="fluent-input" value={values.verbosity} onChange={e => edit({ verbosity: e.target.value as AssistantPreferences["verbosity"] })}><option value="short">Ngắn</option><option value="normal">Vừa</option><option value="long">Dài</option></select></label>
        <label>Định dạng<select className="fluent-input" value={values.format} onChange={e => edit({ format: e.target.value as "text" | "markdown" })}><option value="markdown">Markdown</option><option value="text">Văn bản</option></select></label>
        <label>Tên hiển thị<input className="fluent-input" maxLength={80} value={values.display_name} onChange={e => edit({ display_name: e.target.value })} /></label>
        <label>Xưng hô<input className="fluent-input" maxLength={40} value={values.address_as} onChange={e => edit({ address_as: e.target.value })} /></label>
      </div>
      <label>Chỉ dẫn cá nhân<textarea className="fluent-input" maxLength={2000} value={values.custom_instructions} onChange={e => edit({ custom_instructions: e.target.value })} /></label></fieldset>
      <button type="button" className="fluent-btn-primary my-3" disabled={busy || version === null || Boolean(pending)} onClick={() => void run(prepareSettings)}>Xem trước settings</button>
      <p>Settings lưu độc lập với consent; chỉ consumer đang hỗ trợ và consent theo notice hiện hành mới áp dụng.</p>
      <h3 className="mt-5 font-semibold">Consent theo mục đích</h3>
      {consents.map(value => <div key={value.purpose} className="my-3 rounded-xl border p-3"><p>{purposes[value.purpose]} · {value.current_notice_consented ? "Đã đồng ý notice hiện hành" : "Chưa có consent hiện hành"}</p><button type="button" className="fluent-btn-secondary mt-2" disabled={busy || Boolean(pending)} onClick={() => void run(() => consent(value, value.current_notice_consented ? "WITHDRAWN" : "GRANTED"))}>Xem trước {value.current_notice_consented ? "rút consent" : "cho phép"}</button></div>)}
      <h3 className="mt-5 font-semibold">Quyền đọc và chuẩn bị</h3>
      <p>Phạm vi lấy từ hồ sơ đang mở; không cấp quyền gửi/duyệt hoặc đọc notes riêng.</p>
      <div className="my-3 flex flex-wrap gap-3"><select aria-label="Capability quyền" className="fluent-input" value={capability} onChange={e => setCapability(e.target.value as GrantSpec["capability"])}><option value="read_source">Đọc nguồn</option><option value="read_own_resource" disabled={capabilities?.audience !== "student"}>Đọc hồ sơ của tôi</option><option value="prepare_draft" disabled={capabilities?.audience !== "student"}>Chuẩn bị nháp</option></select><select aria-label="Thời hạn quyền" className="fluent-input" value={lifetime} onChange={e => setLifetime(e.target.value as GrantSpec["lifetime"])}><option value="once">Một lần, tối đa 60 giây</option><option value="session">Phiên, tối đa 60 giây</option><option value="timed">10 phút</option></select><button type="button" className="fluent-btn-secondary" disabled={!runtime.surface.resource || !capabilities?.grants || busy || Boolean(pending)} onClick={() => void run(prepareGrant)}>Xem trước quyền</button></div>
      {grants.map(grant => <div key={grant.id} className="my-3 rounded-xl border p-3 text-sm"><p>{grant.capability} · {grant.state} · {grant.lifetime}</p><p className="break-all">{grant.resource.kind} {grant.resource.id} · phiên bản {grant.resource.expected_version}</p><p>Hết hạn: {grant.expires_at} · Dùng cuối: {grant.last_used_at || "Chưa dùng"} · {grant.use_count} lượt</p>{grant.locked_reason && <p>Khóa: {grant.locked_reason}</p>}<button type="button" className="fluent-btn-secondary mt-2" disabled={grant.state === "revoked" || busy || Boolean(pending)} onClick={() => void run(() => revoke(grant))}>Xem trước rút quyền</button>{grant.capability !== "prepare_draft" && <button type="button" className="fluent-btn-secondary mt-2" disabled={grant.state !== "active" || Boolean(grant.locked_reason) || busy} onClick={() => void run(() => readGranted(grant))}>Đọc projection theo quyền</button>}</div>)}
      {projection && <div className="my-4 rounded-xl border p-3"><p role="status" className="text-xs">Đã đọc có receipt {projection.receipt}; không có quyền ghi nghiệp vụ.</p><AssistantContent content={projection.text} audience={capabilities?.audience} /></div>}
      {grantCursor && <button type="button" disabled={busy} onClick={() => void run(async () => { const page = await service.grants(grantCursor); setGrants(previous => [...previous, ...page.items]); setGrantCursor(page.page.next_cursor); })}>Đọc thêm quyền</button>}
      {!navigation && <p className="my-4"><Link href="/memory" className="underline">Quản lý memory và quên</Link> · <Link href="/notifications" className="underline">Theo dõi và thông báo</Link>. Các trang kiểm consumer hiện hành trước khi ghi; quyền nghiệp vụ và xác nhận gửi/duyệt vẫn thực hiện trong hồ sơ.</p>}
      {pending && <section className="my-4 rounded-xl border border-blue-300 p-4" aria-label="Xem trước thay đổi"><p className="whitespace-pre-wrap">{pending.label}</p><p>Preview hết hạn: {pending.preview.expires_at}</p><label className="my-3 block"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> Tôi xác nhận đúng nội dung và phạm vi trên</label><div className="flex flex-wrap gap-2"><button type="button" className="fluent-btn-primary" disabled={!confirmed || busy} onClick={() => void run(confirm)}>Xác nhận và đọc lại</button><button type="button" className="fluent-btn-secondary" disabled={busy} onClick={() => { setPending(null); setConfirmed(false); }}>Giữ bản soạn, đóng preview</button><button type="button" disabled={busy} onClick={() => void run(async () => { const receipt = await service.receipt(pending.clientId); if (receipt.state !== "committed" || receipt.client_id !== pending.clientId || pending.settings && (!Number.isSafeInteger(receipt.version) || receipt.version < 1)) throw new Error("Chưa có receipt khớp thao tác"); await refreshAfterCommit(pending.settings ? receipt.version : undefined); if (pending.settings) setDirty(false); setMessage(`Đã đọc lại receipt ${receipt.receipt_id}`); setPending(null); })}>Kiểm tra receipt</button></div></section>}
    </SettingsSurface>
  </>;
}
