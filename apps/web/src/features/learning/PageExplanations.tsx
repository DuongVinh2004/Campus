"use client";
import { RefreshCw } from "lucide-react";
import { IconButton } from "@/components/shared/IconButton";

import { useT, type MessageKey } from "@/lib/i18n";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { LearningGateway, type LearningMaterial, type LearningPageExplanation } from "../../lib/data/api/learning-gateway";
import styles from "./learning.module.css";
import { useActorRouteState,useTabDraftOwner } from "../chat/route-drafts";
import {LearningMetadataForm} from './LearningMetadataForm';

const gateway = new LearningGateway();
export const explanationLabels = {
  RETEACH: "pex.1",
  ADD_EXAMPLE: "pex.2",
  CORRECTION: "pex.3",
} as const;
type ExplanationEditor={editing?:LearningPageExplanation;versionId:string;page:number;category:LearningPageExplanation["category"];body:string};
const emptyEditor:ExplanationEditor={versionId:"",page:1,category:"RETEACH",body:""};

export function PageExplanations({ actorId, sessionId, materials, canManage, readerSource, onPublish, onOpen }: {
  actorId: string; sessionId: string; materials: LearningMaterial[]; canManage: boolean;
  readerSource?: { versionId: string; page: number };
  onPublish: (draft: LearningPageExplanation) => Promise<unknown>;
  onOpen: (versionId: string, page: number) => void;
}) {
  const t = useT();
  const translatedLabels = Object.fromEntries(Object.entries(explanationLabels).map(([k, v]) => [k, t(v)]));
  const [rows, setRows] = useState<LearningPageExplanation[]>();
  const owner=useTabDraftOwner();
  const scopeKey=JSON.stringify(["page-explanations",actorId,sessionId]);
  const readScope=JSON.stringify([owner.scope,scopeKey]);
  const [rowsScope,setRowsScope]=useState<string>();
  const visibleRows=rowsScope===readScope?rows:undefined;
  const [editors,setEditors]=useActorRouteState<{active:string;entries:Record<string,ExplanationEditor>}>(owner.scope,scopeKey,()=>({active:"new",entries:{}}));
  const editorKey=editors.active;
  const editor=editors.entries[editorKey]??emptyEditor;
  const {editing,versionId,page,category,body}=editor;
  const updateEditor=(patch:Partial<ExplanationEditor>)=>setEditors(current=>({...current,entries:{...current.entries,[editorKey]:{...(current.entries[editorKey]??emptyEditor),...patch}}}));
  const setVersionId=(versionId:string)=>updateEditor({versionId});
  const setPage=(page:number)=>updateEditor({page});
  const setCategory=(category:LearningPageExplanation["category"])=>updateEditor({category});
  const setBody=(body:string)=>updateEditor({body});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [refresh, setRefresh] = useState(0);
  const lifecycle = useRef<AbortController | null>(null);
  const [attempts,setAttempts]=useActorRouteState<Record<string,string>>(owner.scope,scopeKey+":pending",()=>({}));
  const headers = { "X-Campus-Reader-Actor": actorId };
  const path = `/sessions/${sessionId}/page-explanations`;
  const sources = materials.filter(material => material.visibility === "VISIBLE").flatMap(material =>
    material.versions.filter(version => version.processing_state === "READY" && version.publication_state === "PUBLISHED")
      .map(version => ({ ...version, title: material.title })),
  );
  const source = sources.find(item => item.id === versionId);
  const freshEditing=visibleRows?.find(row=>row.id===editing?.id)??editing;
  const readerIsLinked = readerSource && sources.some(item => item.id === readerSource.versionId);

  useEffect(() => {
    const controller = new AbortController();
    lifecycle.current = controller;
    setBusy(false);
    return () => controller.abort();
  }, [actorId, sessionId,readScope]);

  useEffect(() => {
    const controller = new AbortController();
    setRowsScope(undefined);
    void gateway.list<LearningPageExplanation>(path, controller.signal, { "X-Campus-Reader-Actor": actorId })
      .then(result => { if (!controller.signal.aborted){setRows(result);setRowsScope(readScope);} })
      .catch(caught => { if (!controller.signal.aborted) {
        setRows(undefined);
        setRowsScope(undefined);
        setError(caught instanceof Error ? caught.message : t("pex.4"));
      } });
    return () => controller.abort();
  }, [actorId, path, refresh,readScope]);

  async function perform(work: (signal: AbortSignal) => Promise<unknown>, success: string) {
    if (busy) return;
    const signal = lifecycle.current?.signal;
    if (!signal || signal.aborted) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await work(signal);
      if (!signal?.aborted) { setNotice(success); setRefresh(value => value + 1); }
    } catch (caught) {
      if (!signal?.aborted) setError(caught instanceof Error ? caught.message : t("pex.5"));
    } finally {
      if (lifecycle.current?.signal === signal) setBusy(false);
    }
  }

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const url = editing ? `/page-explanations/${editing.id}` : path;
    const payload = { body, category, ...(editing ? { revision: editing.revision } : { version_id: versionId, page_no: page }) };
    const fingerprint = JSON.stringify([url, payload]);
    const key=attempts[fingerprint]??crypto.randomUUID();
    const submitted=editor;
    setAttempts(current=>({...current,[fingerprint]:key}));
    void perform(async signal => {
      await gateway.write(url, payload, editing ? "PATCH" : "POST", key, headers, signal);
      if (signal.aborted) return;
      setAttempts(current=>{if(current[fingerprint]!==key)return current;const {[fingerprint]:saved,...remaining}=current;return remaining;});
      setEditors(current=>{if(current.entries[editorKey]!==submitted)return current;const {[editorKey]:saved,...remaining}=current.entries;return {active:current.active===editorKey?"new":current.active,entries:remaining};});
    }, t("pex.6"));
  }

  if(owner.enabled&&!owner.scope)return <p role="status">{t("pex.7")}</p>;
  return <section aria-label={t("pex.8")}>
    <h3>{t("pex.8")}</h3>
    {!visibleRows&&!error&&<p role="status">{t("pex.9")}</p>}
    {visibleRows?.length === 0 && <p>{t("pex.10")}</p>}
    {!!visibleRows?.length && <ul className={styles.list}>{visibleRows.map(row => <li key={row.id}>
      <strong>{t(explanationLabels[row.category])}</strong> · {row.status === "DRAFT" ? t("pex.11") : t("pex.12")}
      <p style={{ whiteSpace: "pre-wrap" }}>{row.body}</p>
      <button type="button" onClick={() => onOpen(row.version_id, row.page_no)}>Mở trang nguồn {row.page_no}</button>
      {row.status === "DRAFT" && canManage && <>
        <button type="button" disabled={busy} onClick={() => {
          setEditors(current=>({active:row.id,entries:{...current.entries,[row.id]:current.entries[row.id]??{editing:row,versionId:row.version_id,page:row.page_no,category:row.category,body:row.body}}}));
        }}>{t("pex.13")}</button>
        <button type="button" disabled={busy || editing?.id === row.id}
          onClick={() => void perform(() => onPublish(row), t("pex.14"))}>{t("pex.15")}</button>
      </>}
    </li>)}</ul>}
    {canManage && !!sources.length && editing && freshEditing && <section className={styles.stack} aria-label={t("pex.16")}>
      <h4>{t("pex.16")}</h4>
      <p>Nguồn: {sources.find(row=>row.id===editing.version_id)?.title??t("pex.17")} · Trang {editing.page_no}</p>
      <LearningMetadataForm key={`${owner.scope}:${sessionId}:${editing.id}`} actorId={actorId} draftId={`page-explanation:${sessionId}:${editing.id}`} className={styles.stack} disabled={busy}
      initialValues={{body:freshEditing.body,category:freshEditing.category}} basis={{revision:freshEditing.revision}}
      fieldLabels={{body:t("pex.22"),category:t("pex.21")}} valueLabels={{category:translatedLabels}}
      toPayload={({values,basis})=>({...values,revision:basis.revision})}
      onRead={async signal=>{
        const latest=await gateway.list<LearningPageExplanation>(path,signal,headers);
        const row=latest.find(row=>row.id===editing.id);
        if(!row||row.status!=='DRAFT'||row.version_id!==editing.version_id||row.page_no!==editing.page_no)throw new Error(t("pex.29"));
        return {values:{body:row.body,category:row.category},basis:{revision:row.revision}};
      }}
      onSave={async(payload,key)=>{
        const signal=lifecycle.current?.signal;
        if(!signal||signal.aborted)throw new Error(t("pex.30"));
        setBusy(true);setError('');setNotice('');
        try{
          await gateway.write(`/page-explanations/${editing.id}`,payload,'PATCH',key,headers,signal);
          if(signal.aborted)throw new Error(t("pex.31"));
          setRefresh(value=>value+1);setNotice(t("pex.6"));
        }finally{if(lifecycle.current?.signal===signal)setBusy(false);}
      }}>{(values,change)=><>
        <label>{t("pex.21")}<select value={values.category} onChange={event=>change('category',event.target.value)}>{Object.entries(explanationLabels).map(([value,label])=><option key={value} value={value}>{t(label as MessageKey)}</option>)}</select></label>
        <label>{t("pex.22")}<textarea required maxLength={5000} rows={6} value={values.body} onChange={event=>change('body',event.target.value)}/></label>
        <p>{t("pex.23")}</p>
        <div className={styles.row}>
        <button disabled={!values.body.trim()}>{t("pex.24")}</button>
        <button type="button" onClick={()=>setEditors(current=>({...current,active:'new'}))}>{t("pex.25")}</button>
        </div>
      </>}</LearningMetadataForm></section>}
    {canManage && !!sources.length && !editing && <form className={styles.stack} onSubmit={save}>
      <h4>{editing ? t("pex.16") : t("pex.18")}</h4>
      <div className={styles.form}>
      {!editing && readerIsLinked && <button type="button" disabled={busy}
        onClick={() => { setVersionId(readerSource.versionId); setPage(readerSource.page); }}>{t("pex.19")}</button>}
      <label>{t("pex.27")} <select required value={versionId} disabled={busy || !!editing}
        onChange={event => { setVersionId(event.target.value); setPage(1); }}>
        <option value="">{t("pex.20")}</option>
        {sources.map(item => <option key={item.id} value={item.id}>{item.title} · Bản {item.version_no}</option>)}
      </select></label>
      <label>{t("pex.28")} <input type="number" required min={1} max={source?.page_count ?? 1} value={page}
        disabled={busy || !!editing} onChange={event => setPage(Number(event.target.value))} /></label>
      <label>{t("pex.21")} <select value={category} disabled={busy}
        onChange={event => setCategory(event.target.value as LearningPageExplanation["category"])}>
        {Object.entries(explanationLabels).map(([value, label]) => <option key={value} value={value}>{t(label as MessageKey)}</option>)}
      </select></label>
      </div>
      <label>{t("pex.22")} <textarea value={body} required maxLength={5000} rows={6} disabled={busy}
        onChange={event => setBody(event.target.value)} /></label>
      <p>{t("pex.23")}</p>
      <button disabled={busy || !body.trim() || !versionId}>{t("pex.24")}</button>
      {editing && <button type="button" disabled={busy} onClick={() => setEditors(current=>({...current,active:"new"}))}>{t("pex.25")}</button>}
    </form>}
    {error && <p role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    <IconButton label={t("pex.26")} disabled={busy} onClick={() => { setError(""); setRefresh(value => value + 1); }} icon={<RefreshCw size={17} />} />
  </section>;
}
