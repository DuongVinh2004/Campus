"use client";
import { RefreshCw } from "lucide-react";
import { IconButton } from "@/components/shared/IconButton";

import { useT } from "@/lib/i18n";
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
const fields = { problem: "icx.1", idea: "icx.2", verification: "icx.3", source_description: "icx.4" } as const;

function OwnProse({ value }: { value: Prose }) {
  const t = useT();
  return <dl>{Object.entries(fields).map(([key, label]) => value[key as keyof Prose] && <div key={key}>
    <dt>{t(label)}</dt><dd style={{ whiteSpace: "pre-wrap" }}>{value[key as keyof Prose]}</dd>
  </div>)}</dl>;
}

export function IdeaSourceSummary({ source, onOpen }: { source: IdeaSource | null; onOpen?: (source: IdeaSource) => void }) {
  const t = useT();
  if (!source) return <p>{t("icx.11")}</p>;
  return <div>
    <p>{t("icx.5", { title: source.title, v: source.version_no, p: source.page_no })}</p>
    {source.quote && <blockquote aria-label={t("icx.12")}>{source.quote}</blockquote>}
    {source.kind === "REGION" && <p>{t("icx.13")}</p>}
    {onOpen && <button type="button" onClick={() => onOpen(source)}>{t("icx.14")}</button>}
  </div>;
}

export function IdeaCards({ actorId, canCreate, sourceRequest, onOpen, onShare }: {
  actorId: string; canCreate: boolean;
  sourceRequest?: { sequence: number; selection: ReaderSelection };
  onOpen: (source: IdeaSource) => void;
  onShare: (cardId: string, revision: number, recipientIds: string[]) => Promise<unknown>;
}) {
  const t = useT();
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
  const appliedSource = useRef<{ actorId: string; sequence: number } | undefined>(undefined);
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
          setError(caught instanceof Error ? caught.message : t("icx.15"));
        }
      });
    if (shareId && uuid.test(shareId)) {
      void api.request<Shared>(`/shared-idea-cards/${shareId}`, { headers: actorHeader, signal: controller.signal })
        .then(row => { if (!controller.signal.aborted) setDirect(row); })
        .catch(() => { if (!controller.signal.aborted) { setDirect(undefined); setError(t("icx.16")); } });
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
        setError(caught instanceof Error ? caught.message : t("icx.17"));
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
      }, t("icx.18"));
    } else if (anchor) {
      const source = {
        version_id: anchor.version_id, page_no: anchor.page_no, kind: anchor.anchor.kind,
        ...(anchor.anchor.kind === "TEXT" ? { quote: anchor.anchor.text_quote?.exact } : {}),
        ...(anchor.anchor.kind === "REGION" ? { rects: anchor.anchor.rects } : {}),
      };
      void work(async () => {
        await write("/me/idea-cards", { ...draft, topic_id: topicId || null, source }, "POST");
        saved();
      }, t("icx.19"));
    }
  }
  async function chooseRecipients(card: Card) {
    await work(async () => {
      const rows = await api.list<Recipient>(`/me/idea-cards/${card.id}/recipients`, lifecycle.current?.signal, headers);
      setRecipientCard(card); setEligible(rows); setSelected([]);
    }, "");
  }

  if(owner.enabled&&!owner.scope)return <p role="status">{t("icx.20")}</p>;
  return <section id="learning-idea-cards" aria-label={t("icx.21")} className={styles.panel}>
    <h2>{t("icx.21")}</h2>
    {error && <p role="alert">{badQuote ? t("icx.22") : error}</p>}
    {notice && <p role="status">{notice}</p>}
    {(anchor || editing) && <form className={styles.form} onSubmit={event => { event.preventDefault(); saveCard(); }}>
      <h3 tabIndex={-1} ref={formTitle}>{editing ? t("icx.23") : t("icx.24")}</h3>
      {anchor && <div><p>{t("icx.6", { p: anchor.page_no })} · {anchor.anchor.kind === "PAGE" ? t("icx.25") : anchor.anchor.kind === "TEXT" ? t("icx.26") : t("icx.27")}</p>
        {anchor.anchor.kind !== "PAGE" && <button type="button" onClick={() => {
          editorGeneration.current++;
          setAnchor({ ...anchor, anchor: { kind: "PAGE" } }); setError(""); setBadQuote(false);
        }}>{t("icx.28")}</button>}
      </div>}
      {editing && <IdeaSourceSummary source={editing.source} />}
      <p>{t("icx.29")}</p>
      {(Object.keys(fields) as (keyof Prose)[]).map(key => <label key={key}>{t(fields[key])}
        <textarea value={draft[key]} required={key !== "source_description"} maxLength={key === "source_description" ? 1000 : 2000}
          onChange={event => setDraft({ ...draft, [key]: event.target.value })} disabled={busy} />
      </label>)}
      <label>{t("icx.30")} <select value={topicId} disabled={busy} onChange={event => setTopicId(event.target.value)}>
        <option value="">{t("icx.31")}</option>
        {topics.filter(item => item.status === "ACTIVE" || item.id === topicId).map(item =>
          <option value={item.id} key={item.id}>{item.title}</option>)}
      </select></label>
      <button disabled={busy}>{t("icx.32")}</button>
      <button type="button" disabled={busy} onClick={() => { setEditing(undefined); setAnchor(undefined); }}>{t("icx.33")}</button>
    </form>}
    {(canCreate || topicEdit) && <details><summary>{t("icx.34")}</summary>
      <form className={styles.form} onSubmit={event => {
        event.preventDefault();
        void work(async () => {
          if (topicEdit) await write(`/me/idea-topics/${topicEdit.id}`, { title: topicTitle, revision: topicEdit.revision, status: topicEdit.status }, "PATCH");
          else await write("/me/idea-topics", { title: topicTitle }, "POST");
          setTopicTitle(""); setTopicEdit(undefined);
        }, t("icx.35"));
      }}>
        <label>{t("icx.36")} <input required maxLength={160} value={topicTitle} disabled={busy} onChange={event => setTopicTitle(event.target.value)} /></label>
        <button disabled={busy}>{topicEdit ? t("icx.37") : t("icx.38")}</button>
      </form>
      <ul>{topics.map(item => <li key={item.id}>{item.title} · {item.status === "ARCHIVED" ? t("icx.39") : t("icx.7")}{" "}
        <button type="button" disabled={busy} onClick={() => { setTopicEdit(item); setTopicTitle(item.title); }}>{t("icx.40")}</button>{" "}
        <button type="button" disabled={busy} onClick={() => void work(() => write(`/me/idea-topics/${item.id}`, {
          title: item.title, revision: item.revision, status: item.status === "ACTIVE" ? "ARCHIVED" : "ACTIVE",
        }, "PATCH"), t("icx.41"))}>{item.status === "ACTIVE" ? t("icx.42") : t("icx.43")}</button>
      </li>)}</ul>
    </details>}
    {cards?.length === 0 && <p>{t("icx.44")}</p>}
    {!!cards?.length && <ul className={styles.list}>{cards.map(card => <li key={card.id}>
      <h3>{topics.find(topic => topic.id === card.topic_id)?.title ?? t("icx.31")} · {t("icx.8", { r: card.revision })}</h3>
      {card.status === "ARCHIVED" && <p>{t("icx.39")}</p>}
      <IdeaSourceSummary source={card.source} onOpen={onOpen} />
      <OwnProse value={card} />
      <div className={styles.row}>
        <button type="button" disabled={busy} onClick={() => {
          editorGeneration.current++;
          const key=JSON.stringify([actorId,"card",card.id]);
          setEditors(current=>({active:key,entries:{...current.entries,[key]:current.entries[key]??{
            editing:card,topicId:card.topic_id??"",draft:{problem:card.problem,idea:card.idea,verification:card.verification,source_description:card.source_description}}}}));
        }}>{t("icx.45")}</button>
        <button type="button" disabled={busy} onClick={() => void work(() => write(`/me/idea-cards/${card.id}`, {
          problem: card.problem, idea: card.idea, verification: card.verification, source_description: card.source_description,
          topic_id: card.topic_id, revision: card.revision, status: card.status === "ACTIVE" ? "ARCHIVED" : "ACTIVE",
        }, "PATCH"), t("icx.46"))}>{card.status === "ACTIVE" ? t("icx.47") : t("icx.48")}</button>
        {card.source && card.status === "ACTIVE" && <button type="button" disabled={busy} onClick={() => void chooseRecipients(card)}>{t("icx.49")}</button>}
      </div>
      {recipientCard?.id === card.id && <fieldset disabled={busy}>
        <legend>{t("icx.50")}</legend>
        {eligible.length === 0 && <p>{t("icx.51")}</p>}
        {eligible.map(recipient => <label key={recipient.id}><input type="checkbox" checked={selected.includes(recipient.id)}
          disabled={!selected.includes(recipient.id) && selected.length >= 20}
          onChange={event => setSelected(event.target.checked ? [...selected, recipient.id] : selected.filter(id => id !== recipient.id))} /> {recipient.label}</label>)}
        <button type="button" disabled={!selected.length} onClick={() => void work(async () => {
          await onShare(card.id, recipientCard.revision, selected); setRecipientCard(undefined);
        }, t("icx.52"))}>{t("icx.53")}</button>
        <button type="button" onClick={() => setRecipientCard(undefined)}>{t("icx.54")}</button>
      </fieldset>}
      {shares.filter(share => share.card_id === card.id).map(share => <p key={share.id}>
        {t("icx.9", { r: share.card_revision })} · {share.status === "ACTIVE" ? t("icx.55") : share.status === "SUSPENDED" ? t("icx.56") : t("icx.57")}{" "}
        {share.status !== "WITHDRAWN" && <button type="button" disabled={busy} onClick={() => void work(
          () => write(`/me/idea-shares/${share.id}`, { revision: share.revision }, "PATCH"), t("icx.58"),
        )}>{t("icx.59")}</button>}
      </p>)}
    </li>)}</ul>}
    <h3>{t("icx.60")}</h3>
    {!direct && inbox.length === 0 && <p>{t("icx.61")}</p>}
    <ul className={styles.list}>{(direct ? [direct, ...inbox.filter(item => item.id !== direct.id)] : inbox).map(row => <li key={row.id}>
      <p>{t("icx.10", { r: row.card_revision })}</p>
      <IdeaSourceSummary source={row.source} onOpen={onOpen} />
      <OwnProse value={row} />
    </li>)}</ul>
    <IconButton label={t("icx.62")} disabled={busy} onClick={() => { setError(""); setReload(value => value + 1); }} icon={<RefreshCw size={17} />} />
  </section>;
}

export function IdeaShareSummary({ value }: { value: IdeaSharePreview }) {
  const t = useT();
  return <div><IdeaSourceSummary source={value.card.source} /><OwnProse value={value.card} />
    <p>{t("icx.63")}</p><ul>{value.recipients.map(item => <li key={item.id}>{item.label}</li>)}</ul>
    <p>{t("icx.64")}</p>
  </div>;
}
