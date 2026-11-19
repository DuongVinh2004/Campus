"use client";

import { useEffect, useRef, useState } from "react";
import {
  LearningApiError, LearningGateway, type LearningIdeaCard as Card, type LearningIdeaProse as Prose,
  type LearningIdeaRecipient as Recipient, type LearningIdeaSharePreview as IdeaSharePreview, type LearningIdeaSource as IdeaSource,
} from "../../lib/data/api/learning-gateway";
import type { ReaderSelection } from "./reader/reader-anchors";
import styles from "./learning.module.css";
import { useActorRouteState, useTabDraftOwner } from "../chat/route-drafts";

const api = new LearningGateway();
const uuid = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i;
type Status = "ACTIVE" | "ARCHIVED";
type Topic = { id: string; title: string; status: Status; revision: number };
type Share = { id: string; card_id: string; card_revision: number; revision: number; status: "ACTIVE" | "WITHDRAWN" | "SUSPENDED" };
type Shared = Prose & { id: string; card_revision: number; source: IdeaSource };
const empty: Prose = { problem: "", idea: "", verification: "", source_description: "" };
type Editor = { anchor?: ReaderSelection; editing?: Card; draft: Prose; topicId: string };
type Editors = { active: string; entries: Record<string, Editor> };
const emptyEditor: Editor = { draft: empty, topicId: "" };
const fields = { problem: "Vấn đề", idea: "Ý tưởng", verification: "Cách kiểm chứng", source_description: "Mô tả của bạn về phần nguồn" } as const;

function OwnProse({ value }: { value: Prose }) {
  return <dl>{Object.entries(fields).map(([key, label]) => value[key as keyof Prose] && <div key={key}>
    <dt>{label}</dt><dd style={{ whiteSpace: "pre-wrap" }}>{value[key as keyof Prose]}</dd>
  </div>)}</dl>;
}

export function IdeaSourceSummary({ source, onOpen }: { source: IdeaSource | null; onOpen?: (source: IdeaSource) => void }) {
  if (!source) return <p>Nguồn hiện không khả dụng.</p>;
  return <div>
    <p>Nguồn · {source.title} · Bản {source.version_no} · Trang {source.page_no}</p>
    {source.quote && <blockquote aria-label="Trích từ nguồn">{source.quote}</blockquote>}
    {source.kind === "REGION" && <p>Có vùng đánh dấu trên trang.</p>}
    {onOpen && <button type="button" onClick={() => onOpen(source)}>Mở đúng trang nguồn</button>}
  </div>;
}

export function IdeaCards({ actorId, canCreate, sourceRequest, onOpen, onShare }: {
  actorId: string; canCreate: boolean;
  sourceRequest?: { sequence: number; selection: ReaderSelection };
  onOpen: (source: IdeaSource) => void;
  onShare: (cardId: string, revision: number, recipientIds: string[]) => Promise<unknown>;
}) {
  const [cards, setCards] = useState<Card[]>();
  const [topics, setTopics] = useState<Topic[]>([]);
  const [shares, setShares] = useState<Share[]>([]);
  const [inbox, setInbox] = useState<Shared[]>([]);
  const [direct, setDirect] = useState<Shared>();
  const owner = useTabDraftOwner();
  const [editors, setEditors] = useActorRouteState<Editors>(owner.scope,JSON.stringify(["idea-editors",actorId]),()=>({active:"",entries:{}}));
  const editorKey = editors.active;
  const editor = editors.entries[editorKey] ?? emptyEditor;
  const { anchor, editing, draft, topicId } = editor;
  const updateEditor = (patch: Partial<Editor>) => setEditors(current => ({...current,entries:{...current.entries,
    [editorKey]:{...(current.entries[editorKey]??emptyEditor),...patch}}}));
  const setAnchor = (anchor: ReaderSelection | undefined) => updateEditor({anchor});
  const setEditing = (editing: Card | undefined) => updateEditor({editing});
  const setDraft = (draft: Prose) => updateEditor({draft});
  const setTopicId = (topicId: string) => updateEditor({topicId});
  const [topicDraft,setTopicDraft]=useActorRouteState<{editing?:Topic;title:string}>(owner.scope,JSON.stringify(["idea-topic-draft",actorId]),()=>({title:""}));
  const topicEdit=topicDraft.editing,topicTitle=topicDraft.title;
  const setTopicEdit=(editing:Topic|undefined)=>setTopicDraft(current=>({...current,editing}));
  const setTopicTitle=(title:string)=>setTopicDraft(current=>({...current,title}));
  const [recipientCard, setRecipientCard] = useState<Card>();
  const [eligible, setEligible] = useState<Recipient[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [badQuote, setBadQuote] = useState(false);
  const lifecycle = useRef<AbortController | null>(null);
  const [pending,setPending]=useActorRouteState<Record<string,string>>(owner.scope,JSON.stringify(["idea-pending-writes",actorId]),()=>({}));
  const formTitle = useRef<HTMLHeadingElement>(null);
  const appliedSource = useRef<{ actorId: string; sequence: number }>();
  const editorGeneration = useRef(0);
  const headers = { "X-Campus-Reader-Actor": actorId };

  useEffect(() => {
    const controller = new AbortController();
    lifecycle.current = controller;
    setBusy(false);
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    const actorHeader = { "X-Campus-Reader-Actor": actorId };
    const shareId = new URLSearchParams(window.location.search).get("idea_share");
    const list = <T,>(path: string) => api.list<T>(path, controller.signal, actorHeader);
    setInbox([]); setDirect(undefined);
    void Promise.all([list<Topic>("/me/idea-topics"), list<Card>("/me/idea-cards"), list<Share>("/me/idea-shares"), list<Shared>("/shared-idea-cards")])
      .then(([nextTopics, nextCards, nextShares, nextInbox]) => {
        if (controller.signal.aborted) return;
        setTopics(nextTopics); setCards(nextCards); setShares(nextShares);
        setInbox(nextInbox.filter(item => item.id !== shareId));
      }).catch(caught => {
        if (!controller.signal.aborted) {
          setTopics([]); setCards(undefined); setShares([]); setInbox([]);
          setError(caught instanceof Error ? caught.message : "Chưa mở được phiếu ý tưởng.");
        }
      });
    if (shareId && uuid.test(shareId)) {
      void api.request<Shared>(`/shared-idea-cards/${shareId}`, { headers: actorHeader, signal: controller.signal })
        .then(row => { if (!controller.signal.aborted) setDirect(row); })
        .catch(() => { if (!controller.signal.aborted) { setDirect(undefined); setError("Phiếu chia sẻ không còn khả dụng."); } });
    }
    return () => controller.abort();
  }, [actorId, reload]);
  useEffect(() => {
    const refresh = () => setReload(value => value + 1);
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, []);
  useEffect(() => {
    if (!sourceRequest) return;
    if (appliedSource.current?.actorId === actorId && appliedSource.current.sequence === sourceRequest.sequence) return;
    appliedSource.current = { actorId, sequence: sourceRequest.sequence };
    editorGeneration.current++;
    const key = JSON.stringify([actorId,"source",sourceRequest.selection]);
    setEditors(current => ({active:key,entries:{...current.entries,[key]:current.entries[key]?.anchor
      ?current.entries[key]:{...(current.entries[key]??emptyEditor),anchor:sourceRequest.selection,editing:undefined}}}));
    setBadQuote(false); setError(""); setNotice("");
  }, [actorId, sourceRequest]);
  useEffect(() => { if (anchor || editing) formTitle.current?.focus(); }, [anchor, editing]);

  async function work(effect: () => Promise<unknown>, message: string) {
    if (busy) return;
    setBusy(true); setError(""); setNotice(""); setBadQuote(false);
    const signal = lifecycle.current?.signal;
    const generation = editorGeneration.current;
    try {
      await effect();
      if (!signal?.aborted) { if (editorGeneration.current === generation) setNotice(message); setReload(value => value + 1); }
    } catch (caught) {
      if (!signal?.aborted) {
        setBadQuote(caught instanceof LearningApiError && caught.code === "IDEA_QUOTE_UNVERIFIED");
        setError(caught instanceof Error ? caught.message : "Chưa hoàn thành thao tác.");
      }
    } finally {
      if (lifecycle.current?.signal === signal) setBusy(false);
    }
  }
  async function write(path: string, payload: Record<string, unknown>, method: "POST" | "PATCH") {
    const fingerprint = JSON.stringify([path, payload, method]);
    const key=pending[fingerprint]??crypto.randomUUID();
    setPending(current=>({...current,[fingerprint]:key}));
    const signal = lifecycle.current?.signal;
    const result = await api.write(path, payload, method, key, headers, signal);
    if (signal?.aborted) throw new DOMException("Cancelled", "AbortError");
    setPending(current=>{if(current[fingerprint]!==key)return current;const {[fingerprint]:saved,...remaining}=current;return remaining;});
    return result;
  }
  function saveCard() {
    const submitted = editor;
    const saved = () => setEditors(current => current.entries[editorKey] !== submitted ? current : {
      ...current,entries:{...current.entries,[editorKey]:emptyEditor}});
    if (editing) {
      void work(async () => {
        await write(`/me/idea-cards/${editing.id}`, { ...draft, topic_id: topicId || null, revision: editing.revision, status: editing.status }, "PATCH");
        saved();
      }, "Đã lưu thay đổi.");
    } else if (anchor) {
      const source = {
        version_id: anchor.version_id, page_no: anchor.page_no, kind: anchor.anchor.kind,
        ...(anchor.anchor.kind === "TEXT" ? { quote: anchor.anchor.text_quote?.exact } : {}),
        ...(anchor.anchor.kind === "REGION" ? { rects: anchor.anchor.rects } : {}),
      };
      void work(async () => {
        await write("/me/idea-cards", { ...draft, topic_id: topicId || null, source }, "POST");
        saved();
      }, "Đã lưu phiếu riêng.");
    }
  }
  async function chooseRecipients(card: Card) {
    await work(async () => {
      const rows = await api.list<Recipient>(`/me/idea-cards/${card.id}/recipients`, lifecycle.current?.signal, headers);
      setRecipientCard(card); setEligible(rows); setSelected([]);
    }, "");
  }

  if(owner.enabled&&!owner.scope)return <p role="status">Đang kiểm tra tài khoản trước khi mở nháp ý tưởng…</p>;
  return <section id="learning-idea-cards" aria-label="Phiếu ý tưởng" className={styles.panel}>
    <h2>Phiếu ý tưởng</h2>
    {error && <p role="alert">{badQuote ? "Đoạn chữ chưa đối chiếu được với đúng trang." : error}</p>}
    {notice && <p role="status">{notice}</p>}
    {(anchor || editing) && <form className={styles.form} onSubmit={event => { event.preventDefault(); saveCard(); }}>
      <h3 tabIndex={-1} ref={formTitle}>{editing ? "Sửa phiếu ý tưởng" : "Lưu phiếu riêng"}</h3>
      {anchor && <div><p>Nguồn · Trang {anchor.page_no} · {anchor.anchor.kind === "PAGE" ? "Cả trang" : anchor.anchor.kind === "TEXT" ? "Đoạn chữ chờ đối chiếu" : "Vùng đã chọn"}</p>
        {anchor.anchor.kind !== "PAGE" && <button type="button" onClick={() => {
          editorGeneration.current++;
          setAnchor({ ...anchor, anchor: { kind: "PAGE" } }); setError(""); setBadQuote(false);
        }}>Dẫn cả trang</button>}
      </div>}
      {editing && <IdeaSourceSummary source={editing.source} />}
      <p>Do người viết nhập</p>
      {(Object.keys(fields) as (keyof Prose)[]).map(key => <label key={key}>{fields[key]}
        <textarea value={draft[key]} required={key !== "source_description"} maxLength={key === "source_description" ? 1000 : 2000}
          onChange={event => setDraft({ ...draft, [key]: event.target.value })} disabled={busy} />
      </label>)}
      <label>Đề tài <select value={topicId} disabled={busy} onChange={event => setTopicId(event.target.value)}>
        <option value="">Chưa nhóm</option>
        {topics.filter(item => item.status === "ACTIVE" || item.id === topicId).map(item =>
          <option value={item.id} key={item.id}>{item.title}</option>)}
      </select></label>
      <button disabled={busy}>Lưu phiếu ý tưởng</button>
      <button type="button" disabled={busy} onClick={() => { setEditing(undefined); setAnchor(undefined); }}>Đóng biểu mẫu</button>
    </form>}
    {(canCreate || topicEdit) && <details><summary>Quản lý đề tài</summary>
      <form className={styles.form} onSubmit={event => {
        event.preventDefault();
        void work(async () => {
          if (topicEdit) await write(`/me/idea-topics/${topicEdit.id}`, { title: topicTitle, revision: topicEdit.revision, status: topicEdit.status }, "PATCH");
          else await write("/me/idea-topics", { title: topicTitle }, "POST");
          setTopicTitle(""); setTopicEdit(undefined);
        }, "Đã lưu đề tài.");
      }}>
        <label>Tên đề tài <input required maxLength={160} value={topicTitle} disabled={busy} onChange={event => setTopicTitle(event.target.value)} /></label>
        <button disabled={busy}>{topicEdit ? "Lưu tên đề tài" : "Tạo đề tài"}</button>
      </form>
      <ul>{topics.map(item => <li key={item.id}>{item.title} · {item.status === "ARCHIVED" ? "Đã lưu trữ" : "Đang dùng"}{" "}
        <button type="button" disabled={busy} onClick={() => { setTopicEdit(item); setTopicTitle(item.title); }}>Đổi tên</button>{" "}
        <button type="button" disabled={busy} onClick={() => void work(() => write(`/me/idea-topics/${item.id}`, {
          title: item.title, revision: item.revision, status: item.status === "ACTIVE" ? "ARCHIVED" : "ACTIVE",
        }, "PATCH"), "Đã cập nhật đề tài.")}>{item.status === "ACTIVE" ? "Lưu trữ đề tài" : "Khôi phục đề tài"}</button>
      </li>)}</ul>
    </details>}
    {cards?.length === 0 && <p>Chưa có phiếu riêng. Mở học liệu để chọn nguồn hoặc tạo đề tài trước.</p>}
    {!!cards?.length && <ul className={styles.list}>{cards.map(card => <li key={card.id}>
      <h3>{topics.find(topic => topic.id === card.topic_id)?.title ?? "Chưa nhóm"} · Bản lưu {card.revision}</h3>
      {card.status === "ARCHIVED" && <p>Đã lưu trữ</p>}
      <IdeaSourceSummary source={card.source} onOpen={onOpen} />
      <OwnProse value={card} />
      <div className={styles.row}>
        <button type="button" disabled={busy} onClick={() => {
          editorGeneration.current++;
          const key=JSON.stringify([actorId,"card",card.id]);
          setEditors(current=>({active:key,entries:{...current.entries,[key]:current.entries[key]??{
            editing:card,topicId:card.topic_id??"",draft:{problem:card.problem,idea:card.idea,verification:card.verification,source_description:card.source_description}}}}));
        }}>Sửa phiếu</button>
        <button type="button" disabled={busy} onClick={() => void work(() => write(`/me/idea-cards/${card.id}`, {
          problem: card.problem, idea: card.idea, verification: card.verification, source_description: card.source_description,
          topic_id: card.topic_id, revision: card.revision, status: card.status === "ACTIVE" ? "ARCHIVED" : "ACTIVE",
        }, "PATCH"), "Đã cập nhật phiếu.")}>{card.status === "ACTIVE" ? "Lưu trữ phiếu" : "Khôi phục phiếu"}</button>
        {card.source && card.status === "ACTIVE" && <button type="button" disabled={busy} onClick={() => void chooseRecipients(card)}>Chọn người nhận</button>}
      </div>
      {recipientCard?.id === card.id && <fieldset disabled={busy}>
        <legend>Người nhận trong lớp nguồn</legend>
        {eligible.length === 0 && <p>Chưa có người nhận đủ quyền.</p>}
        {eligible.map(recipient => <label key={recipient.id}><input type="checkbox" checked={selected.includes(recipient.id)}
          disabled={!selected.includes(recipient.id) && selected.length >= 20}
          onChange={event => setSelected(event.target.checked ? [...selected, recipient.id] : selected.filter(id => id !== recipient.id))} /> {recipient.label}</label>)}
        <button type="button" disabled={!selected.length} onClick={() => void work(async () => {
          await onShare(card.id, recipientCard.revision, selected); setRecipientCard(undefined);
        }, "Đã chia sẻ bản chụp. Người nhận có thể mở trong Phiếu nhận được.")}>Xem trước chia sẻ</button>
        <button type="button" onClick={() => setRecipientCard(undefined)}>Đóng danh sách người nhận</button>
      </fieldset>}
      {shares.filter(share => share.card_id === card.id).map(share => <p key={share.id}>
        Chia sẻ bản lưu {share.card_revision} · {share.status === "ACTIVE" ? "Đang cấp quyền" : share.status === "SUSPENDED" ? "Đã đình chỉ" : "Đã rút"}{" "}
        {share.status !== "WITHDRAWN" && <button type="button" disabled={busy} onClick={() => void work(
          () => write(`/me/idea-shares/${share.id}`, { revision: share.revision }, "PATCH"), "Đã rút quyền chia sẻ.",
        )}>Rút chia sẻ</button>}
      </p>)}
    </li>)}</ul>}
    <h3>Phiếu nhận được</h3>
    {!direct && inbox.length === 0 && <p>Chưa có phiếu được chia sẻ.</p>}
    <ul className={styles.list}>{(direct ? [direct, ...inbox.filter(item => item.id !== direct.id)] : inbox).map(row => <li key={row.id}>
      <p>Bản chia sẻ {row.card_revision}</p>
      <IdeaSourceSummary source={row.source} onOpen={onOpen} />
      <OwnProse value={row} />
    </li>)}</ul>
    <button type="button" disabled={busy} onClick={() => { setError(""); setReload(value => value + 1); }}>Tải lại phiếu ý tưởng</button>
  </section>;
}

export function IdeaShareSummary({ value }: { value: IdeaSharePreview }) {
  return <div><IdeaSourceSummary source={value.card.source} /><OwnProse value={value.card} />
    <p>Người nhận</p><ul>{value.recipients.map(item => <li key={item.id}>{item.label}</li>)}</ul>
    <p>Người nhận mở đúng bản lưu đã xem trước khi cả hai còn quyền đọc nguồn. Bạn có thể rút chia sẻ.</p>
  </div>;
}
