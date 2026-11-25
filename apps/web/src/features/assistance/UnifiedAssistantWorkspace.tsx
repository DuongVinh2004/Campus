"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { createPortal } from "react-dom";
import { PanelLeftClose, PanelLeftOpen, RefreshCw, SquarePen, Settings2 } from "lucide-react";
import { IconButton } from "@/components/shared/IconButton";
import { useChatMenu } from "@/components/AppShell";
import { ThemeToggle } from "@/components/ThemeToggle";
import { PanelResizeHandle } from "@/components/shared/PanelResizeHandle";
import { useUnifiedAssistant } from "@/lib/unified-assistant-runtime";
import { assistantClientId, type ActorStatePreview, type ConversationSummary } from "@/lib/assistant-state-service";
import { ChatPanel } from "@/features/chat/ChatPanel";
import { CitationDrawer, type CitationItem } from "@/features/chat/CitationDrawer";
import { AssistantSettingsCenter } from "./AssistantSettingsCenter";
import { AccessibleDialog } from "@/components/shared/AccessibleDialog";
import { StudentPreparationPanel } from "./StudentPreparationPanel";
import { StudentActionCoverage } from "./StudentActionCoverage";
import { HistoryActions } from "./HistoryActions";
import { CompactNotice } from "@/components/shared/CompactNotice";
import { conversationTooltip, groupConversations } from "./conversation-groups";

export function UnifiedAssistantWorkspace({ compact = false }: { compact?: boolean }) {
  const runtime = useUnifiedAssistant(), { active, capabilities } = runtime;
  const menu = useChatMenu();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [drawer, setDrawer] = useState(false), [citationItems, setCitationItems] = useState<CitationItem[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyWidth, setHistoryWidth] = useState(244);
  const [mobileHistory, setMobileHistory] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 959px)");
    setMobileHistory(media.matches); setHistoryOpen(!media.matches);
    const update = () => setMobileHistory(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const initialQuestionHandled = useRef(false);
  const [titles, setTitles] = useState<Record<string, string>>({});
  const [renaming, setRenaming] = useState<string | null>(null);
  const [pending, setPending] = useState<{ preview: ActorStatePreview; value: ConversationSummary; clientId: string } | null>(null);
  const [confirmed, setConfirmed] = useState(false), [saving, setSaving] = useState(false);
  useEffect(() => {
    const id = new URL(window.location.href).searchParams.get("conversation_id");
    if (id && capabilities?.history && active && !active.id && !active.messages.length) void runtime.select(id);
  }, [capabilities?.history]);
  useEffect(() => {
    if (initialQuestionHandled.current || !active || !capabilities) return;
    const question = new URL(window.location.href).searchParams.get("q")?.trim();
    initialQuestionHandled.current = true;
    if (question && !active.id && !active.messages.length && capabilities.audience === "student") {
      runtime.input(question);
      void runtime.send(question);
    }
  }, [active?.localId, capabilities?.audience]);
  async function preview(value: ConversationSummary, patch: Partial<Pick<ConversationSummary, "title" | "pinned" | "archived">>) {
    if (saving) return; setSaving(true);
    try { await runtime.guard(); const next = { ...value, ...patch }; const clientId = assistantClientId();
      const result = await runtime.service.previewConversation(value, next.title, next.pinned, next.archived, clientId);
      await runtime.guard(); setPending({ preview: result, value: next, clientId }); setConfirmed(false); setRenaming(null);
    } catch (failure) { runtime.setError(failure instanceof Error ? failure.message : "Metadata chưa lưu; tiêu đề đang soạn được giữ."); }
    finally { setSaving(false); }
  }
  async function commit(readReceipt = false) {
    if (!pending || saving || !confirmed && !readReceipt) return; setSaving(true);
    try { await runtime.guard(); const receipt = readReceipt ? await runtime.service.receipt(pending.clientId) : (await runtime.service.confirm("conversations", pending.preview, true)).receipt;
      const value = await runtime.service.conversation(pending.value.id); await runtime.guard();
      if (receipt.client_id !== pending.clientId || receipt.namespace !== "conversation_metadata" || value.version < receipt.version) throw new Error("Chưa xác nhận được readback metadata");
      setPending(null); setConfirmed(false); await runtime.refreshCatalog();
      if (active?.id === value.id) await runtime.reload();
    } catch (failure) { runtime.setError(failure instanceof Error ? failure.message : "Chưa xác nhận commit; preview và tiêu đề được giữ."); }
    finally { setSaving(false); }
  }
  const history = <div className="space-y-1 text-sm">
    {capabilities?.history ? <>
      {runtime.archived && <p className="px-3 py-2 text-xs text-slate-500">Hội thoại đã lưu trữ</p>}
      {!runtime.catalog.length && <p className="px-3 py-4 text-slate-500">Chưa có hội thoại{runtime.archived ? " đã lưu trữ" : ""}.</p>}
      {groupConversations(runtime.catalog).map(group => <section key={group.label} aria-label={group.label} className="campus-history-group"><h3>{group.label}</h3>{group.items.map(value => <article key={value.id} data-conversation-row={value.id} data-selected={active?.id === value.id} className={`flex h-10 min-w-0 items-center gap-1 rounded-lg px-2 hover:bg-slate-100 dark:hover:bg-slate-800 ${active?.id === value.id ? "bg-slate-100 dark:bg-slate-800" : ""}`}>
        {renaming === value.id ? <form className="flex min-w-0 flex-1 items-center gap-1" onSubmit={e => { e.preventDefault(); void preview(value, { title: (titles[value.id] ?? value.title).trim() }); }}>
          <input autoFocus aria-label="Tên hội thoại" className="min-w-0 flex-1 rounded border bg-transparent px-2 py-1" maxLength={120} value={titles[value.id] ?? value.title} onChange={e => setTitles(previous => ({ ...previous, [value.id]: e.target.value }))} onKeyDown={e => { if (e.key === "Escape") { e.stopPropagation(); setRenaming(null); } }} />
          <button type="submit" className="shrink-0 p-1" disabled={saving || !(titles[value.id] ?? value.title).trim()}>Lưu</button>
          <button type="button" className="shrink-0 p-1" disabled={saving} onClick={() => setRenaming(null)}>Hủy</button>
        </form> : <>
          <button type="button" disabled={runtime.busy} aria-label={value.title} aria-current={active?.id === value.id ? "true" : undefined} title={conversationTooltip(value)} data-conversation-title className="h-full min-w-0 flex-1 truncate text-left" onClick={() => { void runtime.select(value.id); if (mobileHistory) setHistoryOpen(false); }}>{value.pinned ? "★ " : ""}{value.title}</button>
          {capabilities.history_metadata && <HistoryActions label={`Thao tác hội thoại: ${value.title}`} disabled={saving || Boolean(pending)} actions={[
            { label: "Đổi tên", run: () => setRenaming(value.id) },
            { label: value.pinned ? "Bỏ ghim" : "Ghim", run: () => void preview(value, { pinned: !value.pinned }) },
            { label: value.archived ? "Bỏ lưu trữ" : "Lưu trữ", run: () => void preview(value, { archived: !value.archived }) },
          ]} />}
        </>}
      </article>)}</section>)}
      {runtime.catalogCursor && <button type="button" onClick={() => void runtime.refreshCatalog(runtime.query, runtime.archived, runtime.catalogCursor!)}>Đọc thêm hội thoại</button>}
    </> : <p>Lịch sử chat cho vai trò này chưa có consumer. Trợ giúp hồ sơ chỉ dùng projection được cấp quyền.</p>}
    {pending && <section className="rounded-lg border border-blue-300 p-3"><p>Xem trước: {pending.value.title} · {pending.value.pinned ? "ghim" : "không ghim"} · {pending.value.archived ? "lưu trữ" : "đang mở"}</p><p className="text-xs">Lưu trữ giữ nguyên dữ liệu nguồn. Version {pending.value.version}.</p><label><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> Xác nhận metadata trên</label><div className="mt-2 flex flex-wrap gap-2"><button type="button" disabled={!confirmed || saving} onClick={() => void commit()}>Xác nhận</button><button type="button" disabled={saving} onClick={() => void commit(true)}>Đọc receipt</button><button type="button" disabled={saving} onClick={() => setPending(null)}>Giữ tiêu đề đang soạn</button></div></section>}
  </div>;
  function citations(id?: string) {
    const all = id ? Object.values(active?.citations || {}).find(items => items.some(item => item.citation.citation_id === id)) || [] : Object.values(active?.citations || {}).flat();
    const items: CitationItem[] = all.map(({ citation }) => ({ id: citation.citation_id, sourceId: citation.source_id, title: citation.source_title, documentRef: citation.version_label, quote: citation.quote || "",
      isSimulation: citation.source_status === "SYNTHETIC", validityStatus: ["CURRENT", "SYNTHETIC"].includes(citation.source_status) ? "active" : "stale",
      locator: citation.locator.section_path || citation.locator.paragraph_id || `Trang ${citation.locator.page_start}`,
      canonicalUrl: citation.canonical_uri.startsWith("https://") ? citation.canonical_uri : undefined,
      ...(active?.id ? { sourceBinding: { conversationId: active.id, messageId: Object.keys(active.citations).find(key => active.citations[key].some(item => item.citation.citation_id === citation.citation_id))!, citation } } : {}) }));
    setCitationItems(items); setDrawer(true);
  }
  const conversationControls = active?.id && <div className="flex flex-wrap gap-2 border-b p-2 text-xs"><IconButton label="Đọc lại lịch sử" disabled={runtime.busy} onClick={() => void runtime.reload()} icon={<RefreshCw size={16} />} />{active.cursor && <button type="button" disabled={runtime.busy} onClick={() => void runtime.loadMore()}>Đọc tiếp messages</button>}{active.turnId && <button type="button" disabled={runtime.busy} onClick={() => void runtime.readReceipt()}>Kiểm tra receipt lượt gửi</button>}{active.cursor && <p role="status">Đã khôi phục một phần; đọc hết trước khi tiếp tục.</p>}</div>;
  if (!capabilities || !active || runtime.authenticationRequired) return <section className="m-4 rounded-xl border bg-white p-5 dark:bg-slate-950" aria-label="Kết nối trợ lý">
    <h2 className="mb-2 font-semibold">{runtime.authenticationRequired ? "Đăng nhập để tiếp tục hỏi đáp" : "Kết nối trợ lý học vụ"}</h2>
    <p role={runtime.error ? "alert" : "status"}>{runtime.error || "Đang kiểm tra phiên đăng nhập…"}</p>
    {runtime.error && <div className="mt-4 flex flex-wrap gap-3">
      {runtime.authenticationRequired && <Link className="fluent-btn-primary" href="/login?next=/chat">Đăng nhập lại</Link>}
      <button type="button" className="fluent-btn-secondary" onClick={runtime.retrySession}>Thử kết nối lại</button>
    </div>}
  </section>;
  const toolbar = <>
    <button type="button" aria-label="Cài đặt" title="Cài đặt" className="campus-nav-item" onClick={() => { menu.close(); setSettingsOpen(true); }}><Settings2 size={19} aria-hidden="true" /><span>Cài đặt</span></button>
  </>;
  const settingsNavigation = <div className="space-y-3">
    <ThemeToggle showLabel />
    <div className="grid grid-cols-2 gap-2 text-sm">
      <Link className="fluent-btn-secondary" href="/notifications">Thông báo</Link>
      <Link className="fluent-btn-secondary" href="/privacy">Quyền riêng tư</Link>
      <Link className="fluent-btn-secondary" href="/memory">Bộ nhớ cá nhân</Link>
    </div>
    <p className="text-xs text-slate-500">{runtime.actor?.display_name || "Đã đăng nhập"}{runtime.actor?.student_code ? ` · ${runtime.actor.student_code}` : ""}</p>
    <Link href="/login" className="text-sm underline">Đổi tài khoản</Link>
  </div>;
  const historyColumn = <aside aria-label="Lịch sử theo tài khoản" className="campus-chat-history relative flex h-full min-h-0 shrink-0 flex-col border-r border-slate-200 bg-white p-2 dark:border-slate-800 dark:bg-slate-950" style={{ width: mobileHistory ? "100%" : historyWidth }}>
    <header className="campus-history-heading">
      <button type="button" aria-label="Đóng lịch sử" title="Ẩn danh sách hội thoại" className="campus-history-toggle" onClick={() => setHistoryOpen(false)}><PanelLeftClose className="h-4 w-4" /></button>
      <button type="button" aria-label="Đoạn chat mới" title="Bắt đầu cuộc trò chuyện mới" disabled={runtime.busy} className="campus-new-chat" onClick={() => { runtime.newChat(); if (mobileHistory) setHistoryOpen(false); }}><SquarePen className="h-4 w-4" /><span>Chat mới</span></button>
    </header>
    <div className="campus-history-caption"><h2 id="unified-history-title">Cuộc trò chuyện</h2><HistoryActions label="Tùy chọn danh sách hội thoại" disabled={runtime.busy} actions={[
      { label: runtime.archived ? "Hội thoại đang mở" : "Hội thoại đã lưu trữ", run: () => { runtime.setQuery(""); runtime.setArchived(!runtime.archived); void runtime.refreshCatalog("", !runtime.archived); } },
      ...(capabilities.temporary_chat ? [{ label: "Chat tạm thời mới", run: () => { runtime.temporaryChat(); if (mobileHistory) setHistoryOpen(false); } }] : []),
    ]} /></div>
    <div className="min-h-0 flex-1 overflow-y-auto">{history}</div>
    {!mobileHistory && <PanelResizeHandle label="Đổi độ rộng lịch sử" width={historyWidth} onChange={setHistoryWidth} min={200} max={440} defaultWidth={244} />}
  </aside>;
  return <div className={`campus-unified-assistant relative flex min-h-0 flex-1 flex-col ${compact ? "h-full" : "h-full"}`}>
    {menu.target && createPortal(toolbar, menu.target)}
    <AssistantSettingsCenter controlledOpen={settingsOpen} onClose={() => setSettingsOpen(false)} navigation={settingsNavigation} />
    <div aria-label="Thông báo hội thoại" className="pointer-events-none absolute right-3 top-12 z-40 flex max-w-[min(320px,calc(100%-24px))] flex-col items-end gap-1">
      {runtime.error && <CompactNotice key={`error:${runtime.error}`} title="Chưa hoàn tất yêu cầu" alert>{runtime.error}</CompactNotice>}
      {active.mode === "temporary" && <CompactNotice key={`temporary:${active.localId}`} title="Chat tạm thời">Không dùng bộ nhớ cá nhân. Nội dung lưu vận hành 30 ngày, không hiện trong lịch sử.</CompactNotice>}
    </div>
    <div className="flex min-h-0 flex-1">
      {historyOpen && !mobileHistory && historyColumn}
      <div className="campus-conversation-pane min-w-0 flex-1">
      {(!historyOpen || mobileHistory) && <button type="button" className="campus-history-reopen" aria-label="Mở danh sách hội thoại" title="Mở danh sách hội thoại" onClick={() => setHistoryOpen(true)}><PanelLeftOpen size={18} /></button>}
      <ChatPanel messages={active.messages} isStreaming={runtime.busy} onSendMessage={value => void runtime.send(value)} onStopStreaming={runtime.stop}
      onClearMessages={runtime.newChat} composerValue={active.input} onComposerChange={runtime.input}
      hideHeader
      chatContext={<div className="campus-conversation-context"><span title={active.summary?.title || "Chat mới"}>{!active.id ? active.mode === "temporary" ? "Chat tạm thời mới" : "Chat mới" : active.summary?.title || "Hội thoại đang mở"}</span><HistoryActions label="Thao tác cuộc trò chuyện" actions={[
        { label: "Thông tin hội thoại", run: () => setDetailsOpen(true) },
        { label: "Tiện ích học vụ", run: () => setToolsOpen(true) },
        ...(Object.values(active.citations).flat().length ? [{ label: "Nguồn trích dẫn", run: () => citations() }] : []),
      ]} /></div>}
      onComposerTools={() => setToolsOpen(true)}
      audience={capabilities.audience} initialSidebarOpen={false} disabled={!active.loaded || Boolean(active.cursor) || Boolean(active.summary && !active.summary.can_continue) || capabilities.audience === "staff" && !runtime.surface.resource}
      citationCount={Object.values(active.citations).flat().length} onOpenCitations={() => citations()} onCitationClick={citations} /></div>
    </div>
    <AccessibleDialog open={detailsOpen} onClose={() => setDetailsOpen(false)} labelledBy="conversation-details-title" className="fixed right-3 top-20 w-[min(420px,calc(100vw-24px))] max-h-[75dvh] overflow-y-auto rounded-2xl border bg-white p-5 shadow-xl dark:bg-slate-950">
      <header className="mb-4 flex items-center justify-between gap-3"><h2 id="conversation-details-title" className="font-semibold">Thông tin hội thoại</h2><button type="button" className="fluent-btn-secondary" onClick={() => setDetailsOpen(false)}>Đóng thông tin</button></header>
      <p role="status" className="mb-3 text-sm">{({ local: "Chỉ trong phiên", pending: "Đang chờ xác nhận lưu", saved: "Đã lưu", error: "Lỗi — nội dung đang soạn được giữ", interrupted: "Gián đoạn — cần đọc receipt/lịch sử" })[active.saveState]}{active.receipt ? ` · ${active.receipt.state}` : ""}</p>
      {runtime.error && <CompactNotice key={runtime.error} title="Chưa hoàn tất yêu cầu" alert>{runtime.error}</CompactNotice>}
      {active.mode === "temporary" && <CompactNotice key={active.localId} title="Về chat tạm thời">Chat tạm thời không đọc/ghi personal memory. Nội dung được lưu vận hành 30 ngày, không hiện trong danh sách lịch sử. Không xóa vật lý dữ liệu hoặc backup.</CompactNotice>}
    {!capabilities.stable_turns && capabilities.audience === "student" && <CompactNotice title="Lưu hội thoại bị giới hạn">Writer đang phục vụ chưa hỗ trợ receipt theo client ID. Khi gián đoạn, đọc lại lịch sử trước khi gửi lượt mới.</CompactNotice>}
    {capabilities.coordination?.profile !== "coordination-checkpoint.v1" && <CompactNotice title="Điều phối chưa sẵn sàng">Writer đang phục vụ chưa có checkpoint/receipt điều phối U3. Trợ giúp hồ sơ dùng projection theo quyền hiện tại.</CompactNotice>}
    {active.resourceWork && capabilities.resource_runs === true && <section className="border-b p-2 text-xs"><button type="button" disabled={runtime.busy} onClick={() => void runtime.readResourceWork()}>Đọc lại checkpoint hồ sơ</button><p role="status">Công việc đã lưu một phần · cần mở nguồn của hồ sơ để đối chiếu quy tắc và kiểm tra bắt buộc.</p></section>}
    {active.runId && capabilities.coordination?.read === true && <section className="border-b p-2 text-xs" aria-label="Trạng thái công việc">
      <button type="button" disabled={runtime.busy} onClick={() => void runtime.readRun()}>Đọc trạng thái công việc</button>
      {active.run && <div role="status"><p>{({ running: "Đang xử lý", waiting_user: "Cần làm rõ", partial: "Có kết quả một phần", completed: "Kết quả có receipt", cancelled: "Đã dừng", failed: "Chưa hoàn tất", interrupted: "Gián đoạn", uncertain: "Chưa xác định kết quả" })[active.run.status]}</p>
        <p>{({ wait: "Đọc lại trạng thái sau khi xử lý.", clarify: "Trả lời câu hỏi làm rõ trong ô soạn.", read_receipt: "Đọc receipt và lịch sử; chưa gửi lại tác vụ.", read_sources: "Mở nguồn được trích dẫn để đối chiếu phần còn thiếu.", new_run: "Có thể mở hội thoại mới; công việc cũ được giữ.", none: "Có thể xem kết quả trong lịch sử." })[active.run.continuation?.next_action || "wait"]}</p>
        {active.run.usage && <p>{active.run.usage.model_calls} lượt model · {active.run.usage.tool_calls} lượt đọc/kiểm · {active.run.usage.usage_complete ? "Usage đã nhận" : "Usage chưa đầy đủ"}</p>}
      </div>}
    </section>}
    {conversationControls}
    </AccessibleDialog>
    <AccessibleDialog open={historyOpen && mobileHistory} onClose={() => setHistoryOpen(false)} labelledBy="unified-history-title" className="campus-history-dialog">{historyColumn}</AccessibleDialog>
    <CitationDrawer isOpen={drawer} citations={citationItems} onClose={() => setDrawer(false)} />
    <AccessibleDialog open={toolsOpen} onClose={() => setToolsOpen(false)} labelledBy="assistant-tools-title" className="campus-tools-sheet"><header className="flex items-center justify-between gap-3 p-5"><h2 id="assistant-tools-title" className="font-semibold">Tiện ích học vụ</h2><button type="button" className="fluent-btn-secondary" onClick={() => setToolsOpen(false)}>Đóng</button></header>{conversationControls}<StudentPreparationPanel key={active.localId} /><StudentActionCoverage /></AccessibleDialog>
  </div>;
}
