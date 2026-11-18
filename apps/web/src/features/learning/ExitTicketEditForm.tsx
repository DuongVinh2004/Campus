"use client";

import {LearningGateway,type LearningMaterial,type LearningVisibleExitTicket,type LearningExitTicket} from '../../lib/data/api/learning-gateway';
import {useActorRouteState,useTabDraftOwner} from '../chat/route-drafts';
import {LearningMetadataForm} from './LearningMetadataForm';
import {ExitTicketDraftForm,exitDraftPayload,initialExitFormValues,type ExitFormValues,type ExitPinnedInstruction} from './ExitTickets';
import type {ReadingInstruction} from './ReadingInstructions';
import type {LearningExitWallInput} from '../../lib/data/api/learning-gateway';
import styles from './learning.module.css';

const gateway=new LearningGateway();
type Binding=Pick<ExitFormValues,'versionId'|'page'|'question'|'instruction'>;
type Schedule={zoneId:string;opens:LearningExitWallInput;closes:LearningExitWallInput};
function snapshot(ticket:LearningVisibleExitTicket){
  const values=initialExitFormValues(ticket);
  return {binding:JSON.stringify({versionId:values.versionId,page:values.page,question:values.question,instruction:values.instruction}),
    schedule:JSON.stringify({zoneId:ticket.zone_id,opens:values.opens,closes:values.closes})};
}
const pin=(ticket:LearningVisibleExitTicket)=>ticket.instruction?{versionId:ticket.version_id,instruction:ticket.instruction}:undefined;

export function ExitTicketEditForm({actorId,draft,materials,instructions,source,busy,onSave,onCancel}:{
  actorId:string;draft:LearningVisibleExitTicket;materials:LearningMaterial[];instructions:ReadingInstruction[];source?:{versionId:string;page:number};busy:boolean;
  onSave:(payload:Record<string,unknown>,key:string)=>Promise<unknown>;onCancel:()=>void;
}){
  const owner=useTabDraftOwner(),scope=JSON.stringify(['exit-edit-context',actorId,draft.id]);
  const [readMaterials,setReadMaterials]=useActorRouteState<LearningMaterial[]>(owner.scope,scope+':materials',()=>materials);
  const [pins,setPins]=useActorRouteState<ExitPinnedInstruction[]>(owner.scope,scope+':pins',()=>{const entry=pin(draft);return entry?[entry]:[];});
  return <LearningMetadataForm actorId={actorId} draftId={`exit-ticket-edit:${draft.id}`} className={styles.stack} disabled={busy}
    initialValues={snapshot(draft)} basis={{revision:draft.revision,zoneId:draft.zone_id}}
    fieldLabels={{binding:'Câu hỏi và nguồn gắn kèm',schedule:'Lịch nhận bài'}} renderValue={(name,value)=>{
      if(name==='binding'){
        const current:Binding=JSON.parse(value),material=readMaterials.find(item=>item.versions.some(version=>version.id===current.versionId));
        const version=material?.versions.find(item=>item.id===current.versionId);
        const pinned=pins.find(item=>`${item.instruction.id}:${item.instruction.revision}`===current.instruction&&item.versionId===current.versionId);
        const instruction=instructions.find(item=>`${item.id}:${item.revision}`===current.instruction&&item.version_id===current.versionId);
        return <div className={styles.stack}><p>{current.question}</p><p>{material?.title??'Nguồn đã chọn'} · Bản {version?.version_no??'chưa khả dụng'} · Trang {current.page}</p>
          <p>{current.instruction?`${pinned?.instruction.purpose??instruction?.purpose??'Chỉ dẫn đã chọn'} · Lần ${pinned?.instruction.revision??instruction?.revision??'chưa khả dụng'}`:'Không gắn chỉ dẫn đọc'}</p></div>;
      }
      const current:Schedule=JSON.parse(value);
      return <div><p>Múi giờ lớp {current.zoneId}</p><p>Mở: {current.opens.local.replace('T',' ')}{current.opens.offset_minutes!==undefined?` · Độ lệch UTC ${current.opens.offset_minutes} phút`:''}</p>
        <p>Đóng: {current.closes.local.replace('T',' ')}{current.closes.offset_minutes!==undefined?` · Độ lệch UTC ${current.closes.offset_minutes} phút`:''}</p></div>;
    }}
    toPayload={({values,basis})=>{
      const binding:Binding=JSON.parse(values.binding),schedule:Schedule=JSON.parse(values.schedule);
      if(schedule.zoneId!==basis.zoneId)throw new Error('Múi giờ của nháp và bản đối chiếu không khớp. Nháp vẫn được giữ.');
      return {operation:'EDIT_DRAFT',revision:basis.revision,draft:exitDraftPayload({...binding,opens:schedule.opens,closes:schedule.closes},readMaterials,instructions,schedule.zoneId,draft,pins)};
    }} onSave={onSave}
    onRead={async signal=>{
      const latest=await gateway.request<LearningExitTicket>(`/exit-tickets/${draft.id}`,{signal,headers:{'X-Campus-Reader-Actor':actorId}});
      if(latest.state!=='DRAFT')throw new Error('Phiếu không còn ở trạng thái bản nháp. Nội dung đang soạn vẫn được giữ.');
      if(latest.id!==draft.id||latest.session_id!==draft.session_id)throw new Error('Phản hồi không thuộc phiếu đang sửa. Nháp vẫn được giữ.');
      if(latest.zone_id!==draft.zone_id)throw new Error('Múi giờ của phiếu đã thay đổi. Hãy kiểm tra lại lịch; nháp vẫn được giữ.');
      const fresh=await gateway.list<LearningMaterial>(`/sessions/${latest.session_id}/materials`,signal,{'X-Campus-Reader-Actor':actorId});
      if(!fresh.some(item=>item.visibility==='VISIBLE'&&item.versions.some(version=>version.id===latest.version_id&&version.publication_state==='PUBLISHED'&&version.processing_state==='READY')))throw new Error('Chưa đọc được nguồn mới đủ điều kiện của phiếu. Nháp vẫn được giữ.');
      if(signal.aborted)throw new DOMException('Cancelled','AbortError');
      setReadMaterials(fresh);const entry=pin(latest);
      if(entry)setPins(current=>current.some(item=>item.versionId===entry.versionId&&item.instruction.id===entry.instruction.id&&item.instruction.revision===entry.instruction.revision)?current:[...current,entry]);
      return {values:snapshot(latest),basis:{revision:latest.revision,zoneId:latest.zone_id}};
    }}>
    {(values,change)=>{
      const binding:Binding=JSON.parse(values.binding),schedule:Schedule=JSON.parse(values.schedule);
      return <ExitTicketDraftForm materials={readMaterials} instructions={instructions} zoneId={schedule.zoneId} source={source} draft={draft} busy={busy} onSave={()=>{}} onCancel={onCancel} embedded pinnedInstructions={pins}
        controlledValues={{...binding,opens:schedule.opens,closes:schedule.closes}}
        onValuesChange={patch=>{
          const bindingPatch=Object.fromEntries(Object.entries(patch).filter(([name])=>['versionId','page','question','instruction'].includes(name)));
          const schedulePatch=Object.fromEntries(Object.entries(patch).filter(([name])=>['opens','closes'].includes(name)));
          if(Object.keys(bindingPatch).length)change('binding',previous=>JSON.stringify({...JSON.parse(previous),...bindingPatch}));
          if(Object.keys(schedulePatch).length)change('schedule',previous=>JSON.stringify({...JSON.parse(previous),...schedulePatch}));
        }}/>
    }}
  </LearningMetadataForm>;
}
