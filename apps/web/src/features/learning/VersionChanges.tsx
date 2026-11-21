"use client";

import { useT, type MessageKey } from "@/lib/i18n";
import { useEffect, useState } from "react";
import { LearningGateway, type LearningChangeItem, type LearningChangeMode, type LearningMaterial, type LearningVersion, type LearningVersionChangeSet } from "../../lib/data/api/learning-gateway";
import styles from "./learning.module.css";
import { useActorRouteState, useTabDraftOwner } from "../chat/route-drafts";
import {LearningMetadataComparison,MetadataDraftHistory,type MetadataDraft} from './LearningMetadataComparison';

const api = new LearningGateway();
const modes: Record<LearningChangeMode, MessageKey> = {
  PAGE_MAP: "vcx.1",
  WHOLE_DOCUMENT: "vcx.2",
  UNSPECIFIED: "vcx.3",
};
const kinds = { EDITED: "vcx.4", MOVED: "vcx.5", ADDED: "vcx.6", REMOVED: "vcx.7" } as const;
const pptx = "application/vnd.openxmlformats-officedocument.presentationml.presentation";
const pageLabel = (type?: string): MessageKey => type === pptx ? "vcx.8" : "vcx.pdfpage";
type ChangeStructure={base_version_id:string;mode:LearningChangeMode|'';items:LearningChangeItem[]};
const changeLabels={structure:'Cấu trúc so sánh',reason:'Lý do cập nhật',target_guidance:'Chỉ dẫn đọc độc lập của bản mới'};

export function olderPublishedVersions(material: LearningMaterial, version: LearningVersion) {
  return material.versions.filter(candidate =>
    candidate.version_no < version.version_no && candidate.publication_state === "PUBLISHED" && candidate.processing_state === "READY");
}

export function ChangeDetails({ change, onOpen }: { change: LearningVersionChangeSet; onOpen?: (version: string, page: number) => void }) {
  const t = useT();
  return <div className={styles.stack}>
    {change.base_available ? <>
      <p>{t("vcx.9", { a: change.base_version_no ?? "", b: change.target_version_no })} · {t(modes[change.mode])}</p>
      <p>{change.reason}</p>
    </> : <p>{t("vcx.10", { v: change.target_version_no })}</p>}
    {change.target_guidance && <p>{change.target_guidance}</p>}
    {!!change.items.length && <ul>{change.items.map((item, index) => <li key={index}>
      {item.kind && <strong>{t(kinds[item.kind])} </strong>}{item.description && <span>{item.description}</span>}
      {item.guidance && <p>{item.guidance}</p>}
      <div className={styles.row}>
        {change.base_available && item.old_page && (onOpen && change.base_version_id
          ? <button type="button" onClick={() => onOpen(change.base_version_id!, item.old_page!)}>{t("vcx.12", { p: t(pageLabel(change.base_media_type)), n: item.old_page })}</button>
          : <span>{t("vcx.13", { p: t(pageLabel(change.base_media_type)), n: item.old_page })}</span>)}
        {item.new_page && (onOpen
          ? <button type="button" onClick={() => onOpen(change.target_version_id, item.new_page!)}>{t("vcx.14", { p: t(pageLabel(change.target_media_type)), n: item.new_page })}</button>
          : <span>{t("vcx.15", { p: t(pageLabel(change.target_media_type)), n: item.new_page })}</span>)}
      </div>
    </li>)}</ul>}
  </div>;
}

export function VersionChangeBanner({ versionId, actorId, onOpen }: { versionId: string; actorId: string; onOpen: (version: string, page: number) => void }) {
  const t = useT();
  const owner=useTabDraftOwner();
  const readScope=JSON.stringify([owner.scope,actorId,versionId]);
  const [loadedScope,setLoadedScope]=useState<string>();
  const [change, setChange] = useState<LearningVersionChangeSet | null>();
  const [error, setError] = useState(false);
  useEffect(() => {
    if(owner.enabled&&!owner.scope)return;
    const controller = new AbortController();
    setLoadedScope(undefined);setError(false); setChange(undefined);
    void api.request<{ change_set: LearningVersionChangeSet | null }>(`/versions/${versionId}/change-set`,
      { signal: controller.signal, headers: { "X-Campus-Reader-Actor": actorId } })
      .then(result => { if (!controller.signal.aborted){setChange(result.change_set);setLoadedScope(readScope);} })
      .catch(() => { if (!controller.signal.aborted){setError(true);setLoadedScope(readScope);} });
    return () => controller.abort();
  }, [versionId, actorId,readScope,owner.enabled,owner.scope]);
  if(loadedScope!==readScope||(owner.enabled&&!owner.scope))return null;
  if (error) return <p role="status">{t("vcx.16")}</p>;
  if (!change) return null;
  return <details className={styles.alert}><summary>{t("vcx.17")}</summary><ChangeDetails change={change} onOpen={onOpen} /></details>;
}

export function VersionChangeEditor({ version, material, actorId, onSave }: {
  version: LearningVersion; material: LearningMaterial; actorId: string;
  onSave: (payload: Record<string, unknown>, key: string) => Promise<LearningVersionChangeSet>;
}) {
  const t = useT();
  const candidates = olderPublishedVersions(material, version);
  const defaultBase = candidates.find(item => item.id === material.current_published_version_id)?.id ?? candidates[0]?.id ?? "";
  const owner = useTabDraftOwner();
  const scope = JSON.stringify(["version-change-editor",actorId,material.id,version.id]);
  const readScope = JSON.stringify([owner.scope,scope]);
  const [loadedScope,setLoadedScope] = useState<string>();
  const [open, setOpen] = useActorRouteState(owner.scope,scope+":open",false);
  const [draft,setDraft]=useActorRouteState<MetadataDraft|undefined>(owner.scope,scope+':draft',undefined);
  const [history,setHistory]=useActorRouteState<MetadataDraft[]>(owner.scope,scope+':history',[]);
  const [saving, setSaving] = useActorRouteState(owner.scope,scope+":saving",false);
  const [error, setError] = useActorRouteState(owner.scope,scope+":error","");
  const [notice, setNotice] = useActorRouteState(owner.scope,scope+":notice","");
  const [attempts,setAttempts] = useActorRouteState<Record<string,string>>(owner.scope,scope+":attempts",{});
  const structure:ChangeStructure=draft?JSON.parse(draft.values.structure):{base_version_id:defaultBase,mode:'',items:[]};
  const {base_version_id:baseId,mode,items}=structure;
  const reason=draft?.values.reason??'',guidance=draft?.values.target_guidance??'';
  const valuesFor=(row:LearningVersionChangeSet|null)=>({structure:JSON.stringify({base_version_id:row?row.base_version_id??'':defaultBase,mode:row?.mode??'',items:row?.base_available?row.items:[]}),reason:row?.reason??'',target_guidance:row?.target_guidance??''});
  function updateValues(patch:Record<string,string>){setDraft(current=>current?{...current,values:{...current.values,...patch}}:current);}
  function updateStructure(change:(value:ChangeStructure)=>ChangeStructure){setDraft(current=>current?{...current,values:{...current.values,structure:JSON.stringify(change(JSON.parse(current.values.structure)))}}:current);}
  const setBaseId=(value:string)=>updateStructure(current=>({...current,base_version_id:value}));
  const setMode=(value:LearningChangeMode|'')=>updateStructure(current=>({...current,mode:value}));
  const setItems=(change:(items:LearningChangeItem[])=>LearningChangeItem[])=>updateStructure(current=>({...current,items:change(current.items)}));
  const setReason=(value:string)=>updateValues({reason:value});
  const setGuidance=(value:string)=>updateValues({target_guidance:value});
  const base = candidates.find(item => item.id === baseId);
  useEffect(() => {
    if (!open || (owner.enabled && !owner.scope)) return;
    const controller = new AbortController();
    setLoadedScope(undefined);
    setError("");
    void api.request<{ change_set: LearningVersionChangeSet | null }>(`/versions/${version.id}/change-set`,
      { signal: controller.signal, headers: { "X-Campus-Reader-Actor": actorId } })
      .then(({ change_set: row }) => {
        if (controller.signal.aborted) return;
        if(row&&row.target_version_id!==version.id)throw new Error('Phản hồi không thuộc phiên bản đang sửa.');
        const values=valuesFor(row);
        setDraft(current=>current??{values,basis:{revision:row?.revision??0},originalValues:values});
        setLoadedScope(readScope);
      }).catch(caught => { if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : "Chưa tải được mô tả."); });
    return () => controller.abort();
  }, [actorId, defaultBase, open, version.id, readScope, owner.enabled, owner.scope]);
  if (!candidates.length) return null;
  function updateItem(index: number, patch: LearningChangeItem) {
    setItems(current => current.map((item, i) => i === index ? { ...item, ...patch } : item));
  }
  if(owner.enabled && !owner.scope)return <p role="status">Đang kiểm tra tài khoản trước khi mở mô tả…</p>;
  return <details open={open} onToggle={event => setOpen(event.currentTarget.open)}><summary>Mô tả thay đổi giữa hai bản</summary>
    {error && <p role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {loadedScope !== readScope && !error && <p role="status">Đang đọc mô tả thay đổi…</p>}
    {draft && loadedScope === readScope && <form className={styles.stack} onSubmit={event => {
      event.preventDefault(); if(saving)return;setSaving(true); setError(""); setNotice("");
      const submitted=draft;
      const payload = { revision:draft.basis.revision, base_version_id: baseId, mode, reason, target_guidance: guidance, items: mode === "PAGE_MAP" ? items : [] };
      const fingerprint = JSON.stringify(payload);
      const key=attempts[fingerprint]??crypto.randomUUID();
      setAttempts(current=>({...current,[fingerprint]:key}));
      void onSave(payload, key)
        .then(row => {
          if(!Number.isSafeInteger(row.revision)||row.revision<=Number(submitted.basis.revision))throw new Error('Chưa xác nhận được phiên bản đã lưu. Nháp và khóa thử lại vẫn được giữ.');
          setAttempts(current=>{const {[fingerprint]:saved,...remaining}=current;return saved===key?remaining:current;});
          setDraft(current=>current===submitted?{...current,basis:{revision:row.revision},originalValues:valuesFor(row)}:current);
          setNotice("Máy chủ đã xác nhận lần lưu mô tả.");
        })
        .catch(caught => { setError(caught instanceof Error ? caught.message : "Chưa lưu được mô tả."); })
        .finally(() => setSaving(false));
    }}>
      <fieldset className={styles.stack} disabled={saving} style={{minWidth:0}}>
      <div className={styles.form}>
      <label>Bản trước <select required value={baseId} disabled={saving} onChange={event => setBaseId(event.target.value)}>
        <option value="">Chọn bản trước</option>{candidates.map(item => <option key={item.id} value={item.id}>Bản {item.version_no}</option>)}
      </select></label>
      <label>Phạm vi thay đổi <select required value={mode} disabled={saving} onChange={event => setMode(event.target.value as LearningChangeMode | "")}>
        <option value="">Chọn phạm vi</option>
        {Object.entries(modes).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select></label>
      </div>
      <label>Lý do cập nhật <textarea rows={4} required maxLength={2000} value={reason} disabled={saving} onChange={event => setReason(event.target.value)} /></label>
      <label>Chỉ dẫn đọc độc lập của bản mới <textarea rows={4} maxLength={2000} value={guidance} disabled={saving} onChange={event => setGuidance(event.target.value)} /></label>
      {mode === "PAGE_MAP" && <>
        {items.map((item, index) => <fieldset key={index} disabled={saving}><legend>Thay đổi {index + 1}</legend>
          <label>Loại <select value={item.kind} onChange={event => {
            const kind = event.target.value as keyof typeof kinds;
            updateItem(index, { kind, old_page: kind === "ADDED" ? null : item.old_page, new_page: kind === "REMOVED" ? null : item.new_page,
              guidance: kind === "REMOVED" ? "" : item.guidance });
          }}>{Object.entries(kinds).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          {item.kind !== "ADDED" && <label>Bản trước · {t(pageLabel(base?.source_media_type))}
            <input required type="number" min={1} max={base?.page_count} value={item.old_page ?? ""}
              onChange={event => updateItem(index, { old_page: event.target.value ? Number(event.target.value) : null })} /></label>}
          {item.kind !== "REMOVED" && <label>Bản mới · {t(pageLabel(version.source_media_type))}
            <input required type="number" min={1} max={version.page_count} value={item.new_page ?? ""}
              onChange={event => updateItem(index, { new_page: event.target.value ? Number(event.target.value) : null })} /></label>}
          <label>Mô tả so sánh <textarea required maxLength={1000} value={item.description ?? ""}
            onChange={event => updateItem(index, { description: event.target.value })} /></label>
          {item.kind !== "REMOVED" && <label>Chỉ dẫn riêng cho trang mới <textarea maxLength={1000} value={item.guidance ?? ""}
            onChange={event => updateItem(index, { guidance: event.target.value })} /></label>}
          <button type="button" onClick={() => setItems(current => current.filter((_, i) => i !== index))}>Bỏ mục {index + 1}</button>
        </fieldset>)}
        <button type="button" disabled={saving || items.length >= 100}
          onClick={() => setItems(current => [...current, { kind: "EDITED", description: "" }])}>Thêm thay đổi</button>
      </>}
      <button disabled={saving || !mode || (mode === "PAGE_MAP" && !items.length)}>{version.publication_state === "PUBLISHED" ? "Xem trước đính chính" : "Lưu mô tả thay đổi"}</button>
      </fieldset>
      <LearningMetadataComparison scope={scope} draft={draft} disabled={saving} labels={changeLabels} valueLabels={{}} renderValue={renderChangeValue}
        onRead={async signal=>{
          const {change_set:row}=await api.request<{change_set:LearningVersionChangeSet|null}>(`/versions/${version.id}/change-set`,{signal,headers:{'X-Campus-Reader-Actor':actorId}});
          if(!row)throw new Error('Chưa có mô tả trên máy chủ để đối chiếu. Nháp vẫn được giữ.');
          if(row.target_version_id!==version.id)throw new Error('Phản hồi không thuộc phiên bản đang sửa.');
          if(!row.base_available||!candidates.some(candidate=>candidate.id===row.base_version_id))throw new Error('Bản trước không còn đủ điều kiện để đối chiếu. Nháp vẫn được giữ.');
          return {values:valuesFor(row),basis:{revision:row.revision}};
        }} onCapture={setDraft} onApply={(source,next)=>{if(source!==draft)return;setHistory(current=>[...current,source]);setDraft(next);setError('');setNotice('Chỉ cập nhật bản đang soạn; chưa lưu lên máy chủ.');}}/>
      <MetadataDraftHistory history={history} labels={changeLabels} renderValue={renderChangeValue}/>
    </form>}
  </details>;

  function renderChangeValue(name:string,value:string){
    if(name!=='structure')return undefined;
    const current:ChangeStructure=JSON.parse(value);
    const source=candidates.find(candidate=>candidate.id===current.base_version_id);
    return <div className={styles.stack}>
      <p>Bản trước: {source?`Bản ${source.version_no}`:'Chưa có bản trước khả dụng'} · {current.mode?t(modes[current.mode]):'Chưa chọn phạm vi'}</p>
      {current.items.length>0?<ol>{current.items.map((item,index)=><li key={index}>
        <p>{item.kind?t(kinds[item.kind]):'Chưa chọn loại'} · Bản trước: {item.old_page??'—'} · Bản mới: {item.new_page??'—'}</p>
        <p>{item.description}</p>{item.guidance&&<p>Chỉ dẫn: {item.guidance}</p>}
      </li>)}</ol>:<p>Không có cặp trang.</p>}
    </div>;
  }
}
