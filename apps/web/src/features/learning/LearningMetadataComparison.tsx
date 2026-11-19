"use client";

import {useEffect,useRef,useState,type ReactNode} from 'react';
import {useActorRouteState,useTabDraftOwner} from '../chat/route-drafts';
import styles from './learning.module.css';

export type MetadataSnapshot={values:Record<string,string>;basis:Record<string,unknown>};
export type MetadataDraft=MetadataSnapshot&{originalValues?:Record<string,string>};
export type MetadataValueRenderer=(name:string,value:string)=>ReactNode;

export function MetadataDraftHistory({history,labels={},valueLabels={},renderValue}:{history:MetadataDraft[];labels?:Record<string,string>;valueLabels?:Record<string,Record<string,string>>;renderValue?:MetadataValueRenderer}){
  return history.length>0?<details><summary>Nháp trước khi đối chiếu ({history.length})</summary>
    {history.map((entry,index)=><section key={index} aria-label={`Nháp đã giữ ${index+1}`}>
      <p>Nháp {index+1} · revision {String(entry.basis.revision)}</p>
      <dl style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{Object.entries(entry.values).map(([name,value])=><div key={name}><dt>{labels[name]??name}</dt><dd>{renderValue?.(name,value)??valueLabels[name]?.[value]??(value||'(Trống)')}</dd></div>)}</dl>
    </section>)}
  </details>:null;
}
type Comparison={source:MetadataDraft;latest:MetadataSnapshot;choices:Record<string,'mine'|'server'>};

export function LearningMetadataComparison({scope,draft,disabled,labels,valueLabels,renderValue,onRead,onCapture,onApply}:{
  scope:string;draft:MetadataDraft;disabled:boolean;labels:Record<string,string>;valueLabels:Record<string,Record<string,string>>;
  renderValue?:MetadataValueRenderer;
  onRead:(signal:AbortSignal)=>Promise<MetadataSnapshot>;
  onCapture:(draft:MetadataDraft)=>void;onApply:(source:MetadataDraft,next:MetadataDraft)=>void;
}){
  const owner=useTabDraftOwner();
  const [comparison,setComparison]=useActorRouteState<Comparison|undefined>(owner.scope,scope+':comparison',undefined);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useActorRouteState(owner.scope,scope+':comparison-error','');
  const request=useRef<AbortController|null>(null);
  useEffect(()=>{setLoading(false);return()=>{request.current?.abort();};},[owner.scope,scope]);
  const current=comparison?.source===draft?comparison:undefined;
  const fields=Object.keys(draft.values);
  const original=draft.originalValues??draft.values;
  const display=(name:string,value:string)=>renderValue?.(name,value)??valueLabels[name]?.[value]??(value||'(Trống)');
  const conflicting=(name:string)=>!!current&&draft.values[name]!==current.latest.values[name]&&(!draft.originalValues||(draft.values[name]!==original[name]&&current.latest.values[name]!==original[name]));
  return <section className={styles.stack} aria-label="Đối chiếu thay đổi">
    <button type="button" disabled={disabled||loading} onClick={()=>{
      request.current?.abort();const controller=new AbortController();request.current=controller;
      onCapture(draft);setComparison(undefined);setError('');setLoading(true);
      void Promise.resolve().then(()=>onRead(controller.signal)).then(latest=>{
        if(controller.signal.aborted)return;
        if(fields.some(name=>typeof latest.values[name]!=='string')||!Number.isSafeInteger(latest.basis.revision)||Number(latest.basis.revision)<1||Number(latest.basis.revision)<Number(draft.basis.revision))throw new Error('Bản trên máy chủ chưa đủ thông tin để đối chiếu.');
        setComparison({source:draft,latest,choices:{}});
      }).catch(caught=>{if(!controller.signal.aborted)setError(caught instanceof Error?caught.message:'Chưa đọc được bản trên máy chủ.');})
        .finally(()=>{if(request.current===controller)setLoading(false);});
    }}>{loading?'Đang đọc bản trên máy chủ…':'Đối chiếu bản trên máy chủ'}</button>
    {error&&<p role="alert">{error}</p>}
    {current&&<>
      <p>Đối chiếu chưa ghi thay đổi lên máy chủ. Chọn nội dung ở các trường xung đột, rồi tiếp tục soạn và xem trước.</p>
      <p>Phiên bản dữ liệu: {String(draft.basis.revision)} → {String(current.latest.basis.revision)}</p>
      {fields.map(name=><section key={name} className={styles.panel} aria-label={`Đối chiếu: ${labels[name]??name}`}>
        <strong>{labels[name]??name}</strong>
        <dl style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>
          <dt>Lúc bắt đầu sửa</dt><dd>{draft.originalValues?display(name,original[name]):'(Chưa có bản gốc)'}</dd>
          <dt>Nháp của bạn</dt><dd>{display(name,draft.values[name])}</dd>
          <dt>Bản trên máy chủ</dt><dd>{display(name,current.latest.values[name])}</dd>
        </dl>
        {conflicting(name)&&<label>Chọn nội dung: {labels[name]??name}<select value={current.choices[name]??''} disabled={disabled||loading} onChange={event=>{
          const choice=event.target.value as 'mine'|'server'|'';
          setComparison(value=>value===current?{...value,choices:{...value.choices,[name]:choice as 'mine'|'server'}}:value);
        }}><option value="">Chưa chọn</option><option value="mine">Giữ nháp của tôi</option><option value="server">Dùng bản trên máy chủ</option></select></label>}
      </section>)}
      <button type="button" disabled={disabled||loading||fields.some(name=>conflicting(name)&&!current.choices[name])} onClick={()=>{
        const values=Object.fromEntries(fields.map(name=>[name,conflicting(name)
          ?current.choices[name]==='mine'?draft.values[name]:current.latest.values[name]
          :draft.values[name]!==original[name]?draft.values[name]:current.latest.values[name]]));
        onApply(draft,{values,basis:current.latest.basis,originalValues:current.latest.values});setComparison(undefined);setError('');
      }}>Dùng kết quả đối chiếu để soạn tiếp</button>
    </>}
  </section>;
}
