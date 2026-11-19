"use client";

import {useRef,type ReactNode} from "react";
import { useActorRouteState, useTabDraftOwner } from "../chat/route-drafts";
import styles from "./learning.module.css";
import {LearningMetadataComparison,MetadataDraftHistory,type MetadataDraft,type MetadataSnapshot,type MetadataValueRenderer} from './LearningMetadataComparison';

type Draft = MetadataDraft;

export function LearningMetadataForm({actorId,draftId,initialValues,basis={},className,disabled=false,clearOnSuccess=true,toPayload,onSave,onRead,fieldLabels={},valueLabels={},renderValue,children}:{
  actorId:string;draftId:string;initialValues:Record<string,string>;basis?:Record<string,unknown>;
  className?:string;disabled?:boolean;clearOnSuccess?:boolean;
  toPayload:(draft:Draft)=>Record<string,unknown>;
  onSave:(payload:Record<string,unknown>,key:string)=>Promise<unknown>;
  onRead?:(signal:AbortSignal)=>Promise<MetadataSnapshot>;fieldLabels?:Record<string,string>;valueLabels?:Record<string,Record<string,string>>;
  renderValue?:MetadataValueRenderer;
  children:(values:Record<string,string>,change:(name:string,value:string|((previous:string)=>string))=>void,basis:Record<string,unknown>)=>ReactNode;
}){
  const owner=useTabDraftOwner();
  const scope=JSON.stringify(['learning-metadata',actorId,draftId]);
  const [retained,setRetained,readRetained]=useActorRouteState<Draft|undefined>(owner.scope,scope+':draft',undefined);
  const [busy,setBusy,readBusy]=useActorRouteState(owner.scope,scope+':busy',false);
  const [,setKeys,readKeys]=useActorRouteState<Record<string,string>>(owner.scope,scope+':keys',{});
  const pending=useRef(new Set<string>()),requestScope=JSON.stringify([owner.scope,scope]);
  const [error,setError]=useActorRouteState(owner.scope,scope+':error','');
  const [history,setHistory]=useActorRouteState<Draft[]>(owner.scope,scope+':history',[]);
  const draft=retained??{values:initialValues,basis,originalValues:initialValues};
  if(owner.enabled&&!owner.scope)return <p role="status">Đang kiểm tra tài khoản trước khi mở biểu mẫu…</p>;
  return <form className={styles.stack} onSubmit={event=>{
    event.preventDefault();if(readBusy()||pending.current.has(requestScope)||disabled)return;
    const submitted=readRetained()??draft;
    let payload:Record<string,unknown>;
    try{payload=toPayload(submitted);}catch(caught){setError(caught instanceof Error?caught.message:'Kiểm tra thông tin đang nhập.');return;}
    const stamp=JSON.stringify(payload),key=readKeys()[stamp]??crypto.randomUUID();
    pending.current.add(requestScope);
    setRetained(submitted);setKeys(current=>({...current,[stamp]:key}));setBusy(true);setError('');
    void Promise.resolve().then(()=>onSave(payload,key)).then(()=>{
      if(clearOnSuccess)setRetained(current=>current?.values===submitted.values?undefined:current);
      setKeys(current=>{const {[stamp]:saved,...rest}=current;return saved===key?rest:current;});
    }).catch(caught=>setError(caught instanceof Error?caught.message:'Chưa lưu được thay đổi.'))
      .finally(()=>{pending.current.delete(requestScope);setBusy(false);});
  }}>
    <fieldset className={className??styles.stack} style={{minWidth:0}} disabled={busy||disabled}>
      {children(draft.values,(name,value)=>setRetained(current=>{const previous=current??draft;return {...previous,values:{...previous.values,[name]:typeof value==='function'?value(previous.values[name]):value}};}),draft.basis)}
    </fieldset>
    {error&&<p role="alert">{error}</p>}
    {onRead&&<LearningMetadataComparison scope={scope} draft={draft} disabled={busy||disabled} labels={fieldLabels} valueLabels={valueLabels} renderValue={renderValue} onRead={onRead}
      onCapture={setRetained} onApply={(source,next)=>{
        if(source!==draft)return;
        setHistory(current=>[...current,source]);setRetained(next);setError('');
      }}/>}
    <MetadataDraftHistory history={history} labels={fieldLabels} valueLabels={valueLabels} renderValue={renderValue}/>
  </form>;
}
