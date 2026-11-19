import React from 'react';
import '@testing-library/jest-dom/vitest';
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {ExitTicketDetail} from './ExitTicketDetail';
import {ExitTicketDraftForm} from './ExitTickets';
import {ChatDraftActor,ChatDraftSessionProvider} from '../chat/route-drafts';
import type {LearningMaterial,LearningVisibleExitTicket} from '../../lib/data/api/learning-gateway';
import type {ReadingInstruction} from './ReadingInstructions';
const id='00000000-0000-4000-8000-000000000011',v1='00000000-0000-4000-8000-000000000012',v2='00000000-0000-4000-8000-000000000013';
const instruction1='00000000-0000-4000-8000-000000000014',instruction2='00000000-0000-4000-8000-000000000015';
const materials:LearningMaterial[]=[{id:'material',offering_id:'offering',title:'Synthetic source',description:'',visibility:'VISIBLE',revision:1,current_published_version_id:v2,
  versions:[v1,v2].map((version,index)=>({id:version,version_no:index+1,processing_state:'READY',publication_state:'PUBLISHED',page_count:4,has_text_layer:true,revision:1}))}];
const instructions:ReadingInstruction[]=[{id:instruction1,version_id:v1,page_ranges:[{start:1,end:1}],purpose:'Original pinned instruction',timing:'BEFORE',questions:[],revision:1},
  {id:instruction2,version_id:v2,page_ranges:[{start:2,end:2}],purpose:'Latest pinned instruction',timing:'BEFORE',questions:[],revision:2}];
const wall=(local:string)=>({local,offset_minutes:420,utc:new Date(Date.parse(local+'Z')-420*60000).toISOString()});
let model:LearningVisibleExitTicket;
let writes:{payload:any;key:string|null}[];
let uncertain=false;
beforeEach(()=>{
  uncertain=false;writes=[];model={id,session_id:'session',revision:3,state:'DRAFT',version_id:v1,page_no:1,question:'Original saved question',zone_id:'Asia/Bangkok',
    opens:wall('2030-11-01T09:00'),closes:wall('2030-11-01T10:00'),instruction:{id:instruction1,revision:1,purpose:'Original pinned instruction',page_ranges:[{start:1,end:1}]}};
  vi.spyOn(globalThis,'fetch').mockImplementation(async(input,init)=>{
    if(String(input).split('?')[0].endsWith('/materials'))return new Response(JSON.stringify({items:materials}));
    if(init?.method==='PATCH'){
      const payload=JSON.parse(String(init.body));writes.push({payload,key:new Headers(init.headers).get('Idempotency-Key')});
      if(uncertain)return new Response(JSON.stringify({code:'UNAVAILABLE'}),{status:503});
      if(payload.revision!==model.revision)return new Response(JSON.stringify({code:'REVISION_CONFLICT'}),{status:409});
      const updated=payload.draft,linked=instructions.find(item=>item.id===updated.instruction?.id&&item.revision===updated.instruction?.revision);
      model={...model,...updated,opens:wall(updated.opens.local),closes:wall(updated.closes.local),instruction:linked?{id:linked.id,revision:linked.revision,purpose:linked.purpose,page_ranges:linked.page_ranges}:null,revision:model.revision+1};return new Response(JSON.stringify(model));
    }
    return new Response(JSON.stringify(model));
  });
});
afterEach(()=>{cleanup();vi.restoreAllMocks();});
function Root({show=true,actor='teacher'}:{show?:boolean;actor?:string}){return <ChatDraftSessionProvider><ChatDraftActor value={actor+'-role'}>{show&&<ExitTicketDetail actorId={actor} ticketId={id} staff canManage materials={materials} instructions={instructions} zoneId='Asia/Bangkok' onClose={()=>{}} onOpen={()=>{}} onChange={()=>{}} confirmWrite={async()=>{}}/>}</ChatDraftActor></ChatDraftSessionProvider>;}
async function open(){fireEvent.click(await screen.findByRole('button',{name:'Sửa bản nháp'}));}
it.each(['mine','server'])('keeps question, page, version and pinned instruction together when choosing %s',async choice=>{
  const view=render(<Root/>);await open();fireEvent.change(screen.getByLabelText('Câu hỏi vận dụng'),{target:{value:'My source-bound question'}});
  model={...model,revision:4,version_id:v2,page_no:2,question:'New source-bound question',closes:wall('2030-11-01T11:00'),instruction:{id:instruction2,revision:2,purpose:'Latest pinned instruction',page_ranges:[{start:2,end:2}]}};
  fireEvent.click(screen.getByRole('button',{name:'Đối chiếu bản trên máy chủ'}));await screen.findByLabelText('Chọn nội dung: Câu hỏi và nguồn gắn kèm');
  expect(screen.getByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'})).toBeDisabled();expect(writes).toHaveLength(0);
  fireEvent.change(screen.getByLabelText('Chọn nội dung: Câu hỏi và nguồn gắn kèm'),{target:{value:choice}});fireEvent.click(screen.getByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'}));
  expect(screen.getByLabelText('Câu hỏi vận dụng')).toHaveValue(choice==='mine'?'My source-bound question':'New source-bound question');
  expect(screen.getByLabelText('Giờ đóng (Asia/Bangkok)')).toHaveValue('2030-11-01T11:00');
  view.rerender(<Root show={false}/>);view.rerender(<Root/>);await screen.findByLabelText('Câu hỏi vận dụng');
  expect(within(screen.getByRole('region',{name:'Nháp đã giữ 1',hidden:true})).getByText('My source-bound question')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Lưu bản nháp'}));await waitFor(()=>expect(writes).toHaveLength(1));
  expect(writes[0].payload).toMatchObject({operation:'EDIT_DRAFT',revision:4,draft:{question:choice==='mine'?'My source-bound question':'New source-bound question',version_id:choice==='mine'?v1:v2,page_no:choice==='mine'?1:2,instruction:{id:choice==='mine'?instruction1:instruction2,revision:choice==='mine'?1:2},closes:{local:'2030-11-01T11:00'}}});
});
it('requires one choice for the complete opening and closing schedule',async()=>{
  render(<Root/>);await open();fireEvent.change(screen.getByLabelText('Giờ mở (Asia/Bangkok)'),{target:{value:'2030-11-01T10:00'}});fireEvent.change(screen.getByLabelText('Giờ đóng (Asia/Bangkok)'),{target:{value:'2030-11-01T12:00'}});
  model={...model,revision:4,opens:wall('2030-11-01T09:15'),closes:wall('2030-11-01T09:45')};
  fireEvent.click(screen.getByRole('button',{name:'Đối chiếu bản trên máy chủ'}));await screen.findByLabelText('Chọn nội dung: Lịch nhận bài');
  fireEvent.change(screen.getByLabelText('Chọn nội dung: Lịch nhận bài'),{target:{value:'mine'}});fireEvent.click(screen.getByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'}));
  expect(screen.getByLabelText('Giờ mở (Asia/Bangkok)')).toHaveValue('2030-11-01T10:00');expect(screen.getByLabelText('Giờ đóng (Asia/Bangkok)')).toHaveValue('2030-11-01T12:00');
});
it('retains a coherent source and both times when several changes share one event batch',async()=>{
  render(<Root/>);await open();act(()=>{
    fireEvent.change(screen.getByLabelText('Phiên bản nguồn'),{target:{value:v2}});fireEvent.change(screen.getByLabelText('Trang nguồn'),{target:{value:'3'}});
    fireEvent.change(screen.getByLabelText('Câu hỏi vận dụng'),{target:{value:'Batched complete edit'}});fireEvent.change(screen.getByLabelText('Giờ mở (Asia/Bangkok)'),{target:{value:'2030-11-01T10:00'}});fireEvent.change(screen.getByLabelText('Giờ đóng (Asia/Bangkok)'),{target:{value:'2030-11-01T12:00'}});
  });fireEvent.click(screen.getByRole('button',{name:'Lưu bản nháp'}));await waitFor(()=>expect(writes).toHaveLength(1));
  expect(writes[0].payload.draft).toMatchObject({version_id:v2,page_no:3,question:'Batched complete edit',instruction:null,opens:{local:'2030-11-01T10:00'},closes:{local:'2030-11-01T12:00'}});
});
it('refuses to adopt a ticket that has left DRAFT while retaining the local prose',async()=>{
  render(<Root/>);await open();fireEvent.change(screen.getByLabelText('Câu hỏi vận dụng'),{target:{value:'Keep unpublished edit'}});model={...model,revision:4,state:'SCHEDULED'};
  fireEvent.click(screen.getByRole('button',{name:'Đối chiếu bản trên máy chủ'}));await screen.findByText('Phiếu không còn ở trạng thái bản nháp. Nội dung đang soạn vẫn được giữ.');
  expect(screen.getByLabelText('Câu hỏi vận dụng')).toHaveValue('Keep unpublished edit');expect(writes).toHaveLength(0);
});
it('retries an uncertain edit with the original payload and key after closing and reopening',async()=>{
  uncertain=true;const view=render(<Root/>);await open();fireEvent.change(screen.getByLabelText('Câu hỏi vận dụng'),{target:{value:'Uncertain source-bound edit'}});fireEvent.click(screen.getByRole('button',{name:'Lưu bản nháp'}));await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button',{name:'Quay lại'}));model={...model,revision:4};fireEvent.click(screen.getByRole('button',{name:'Sửa bản nháp'}));view.rerender(<Root show={false}/>);view.rerender(<Root/>);await screen.findByLabelText('Câu hỏi vận dụng');
  fireEvent.click(screen.getByRole('button',{name:'Lưu bản nháp'}));await waitFor(()=>expect(writes).toHaveLength(2));expect(writes[1]).toEqual(writes[0]);expect(writes[1].payload.revision).toBe(3);
});

it('keeps the local draft when the authorized source-list read is denied',async()=>{
  const original=vi.mocked(fetch).getMockImplementation()!;render(<Root/>);await open();fireEvent.change(screen.getByLabelText('Câu hỏi vận dụng'),{target:{value:'Private draft before source denial'}});
  vi.mocked(fetch).mockImplementation(async(input,init)=>String(input).includes('/materials')?new Response(JSON.stringify({code:'FORBIDDEN'}),{status:403}):original(input,init));
  fireEvent.click(screen.getByRole('button',{name:'Đối chiếu bản trên máy chủ'}));await screen.findByText('Bạn không có quyền thực hiện thao tác này.');
  expect(screen.getByLabelText('Câu hỏi vận dụng')).toHaveValue('Private draft before source denial');expect(screen.queryByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'})).toBeNull();expect(writes).toHaveLength(0);
});

it('ignores a late source-list response after switching the private draft owner',async()=>{
  const original=vi.mocked(fetch).getMockImplementation()!;let finish!:(response:Response)=>void;let hold=true;
  vi.mocked(fetch).mockImplementation(async(input,init)=>{
    if(String(input).includes('/materials')&&hold){hold=false;return new Promise(resolve=>{finish=resolve;});}
    return original(input,init);
  });
  const view=render(<Root/>);await open();fireEvent.change(screen.getByLabelText('Câu hỏi vận dụng'),{target:{value:'Private owner A edit'}});fireEvent.click(screen.getByRole('button',{name:'Đối chiếu bản trên máy chủ'}));await waitFor(()=>expect(finish).toBeTypeOf('function'));
  view.rerender(<Root actor='teacher-b'/>);await open();fireEvent.change(screen.getByLabelText('Câu hỏi vận dụng'),{target:{value:'Private owner B edit'}});
  await act(async()=>finish(new Response(JSON.stringify({items:materials}))));expect(screen.getByLabelText('Câu hỏi vận dụng')).toHaveValue('Private owner B edit');expect(screen.queryByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'})).toBeNull();
  view.rerender(<Root/>);expect(await screen.findByLabelText('Câu hỏi vận dụng')).toHaveValue('Private owner A edit');
});

it('updates source choices from a fresh authorized read before adopting a newly linked version',async()=>{
  const newer='00000000-0000-4000-8000-000000000016';const original=vi.mocked(fetch).getMockImplementation()!;
  render(<Root/>);await open();fireEvent.change(screen.getByLabelText('Giờ đóng (Asia/Bangkok)'),{target:{value:'2030-11-01T12:00'}});
  model={...model,revision:4,version_id:newer,page_no:3,question:'Question on newly linked source',instruction:null};
  vi.mocked(fetch).mockImplementation(async(input,init)=>String(input).includes('/materials')?new Response(JSON.stringify({items:[{...materials[0],versions:[...materials[0].versions,{...materials[0].versions[0],id:newer,version_no:3}]}]})):original(input,init));
  fireEvent.click(screen.getByRole('button',{name:'Đối chiếu bản trên máy chủ'}));await screen.findByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'});fireEvent.click(screen.getByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'}));
  expect(screen.getByLabelText('Phiên bản nguồn')).toHaveValue(newer);expect(screen.getByLabelText('Trang nguồn')).toHaveValue(3);expect(screen.getByLabelText('Giờ đóng (Asia/Bangkok)')).toHaveValue('2030-11-01T12:00');
});

it('does not silently remove a selected reading reference after its option is no longer available',()=>{
  const save=vi.fn();function Create({available=true}:{available?:boolean}){return <ChatDraftSessionProvider><ChatDraftActor value='teacher'><ExitTicketDraftForm materials={materials} instructions={available?instructions:[]} zoneId='Asia/Bangkok' source={{versionId:v1,page:1}} busy={false} draftScope='new-ticket' onSave={save} onCancel={()=>{}}/></ChatDraftActor></ChatDraftSessionProvider>;}
  const view=render(<Create/>);fireEvent.change(screen.getByLabelText('Câu hỏi vận dụng'),{target:{value:'Keep the selected source reference'}});fireEvent.change(screen.getByLabelText('Giờ mở (Asia/Bangkok)'),{target:{value:'2030-11-01T09:00'}});fireEvent.change(screen.getByLabelText('Giờ đóng (Asia/Bangkok)'),{target:{value:'2030-11-01T10:00'}});fireEvent.change(screen.getByLabelText('Chỉ dẫn đọc gắn kèm'),{target:{value:instruction1+':1'}});
  expect(screen.getByRole('button',{name:'Lưu bản nháp'})).toBeEnabled();view.rerender(<Create available={false}/>);
  expect(screen.getByRole('button',{name:'Lưu bản nháp'})).toBeDisabled();expect(screen.getByRole('alert')).toHaveTextContent('Chỉ dẫn đọc không còn phù hợp');expect(save).not.toHaveBeenCalled();
});
