import React from 'react';
import '@testing-library/jest-dom/vitest';
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {ReadingInstructions} from './ReadingInstructions';
import {PageExplanations} from './PageExplanations';
import {ChatDraftActor,ChatDraftSessionProvider} from '../chat/route-drafts';
import type {LearningMaterial} from '../../lib/data/api/learning-gateway';
const version='00000000-0000-4000-8000-000000000002';
const id='00000000-0000-4000-8000-000000000003';
const materials:LearningMaterial[]=[{id:'material',offering_id:'offering',title:'Synthetic source',description:'',visibility:'VISIBLE',revision:1,
  current_published_version_id:version,versions:[{id:version,version_no:1,processing_state:'READY',publication_state:'PUBLISHED',page_count:3,has_text_layer:true,revision:1}]}];
let revision:number,purpose:string,body:string,questions:string[],category:string;
let writes:{path:string;payload:Record<string,unknown>;key:string|null}[];
function row(kind:'instruction'|'explanation'){
  return kind==='instruction'?{id,version_id:version,page_ranges:[{start:1,end:2}],purpose,timing:'BEFORE',questions,revision}
    :{id,version_id:version,page_no:1,category,body,status:'DRAFT',revision};
}
beforeEach(()=>{
  revision=3;purpose='Saved purpose';body='Saved explanation';questions=['Saved question'];category='RETEACH';writes=[];
  vi.spyOn(globalThis,'fetch').mockImplementation(async(input,init)=>{
    const path=String(input),kind=path.includes('reading-instructions')?'instruction':'explanation';
    if(init?.method==='PATCH'){
      const payload=JSON.parse(String(init.body));
      writes.push({path,payload,key:new Headers(init.headers).get('Idempotency-Key')});
      if(payload.revision!==revision)return new Response(JSON.stringify({code:'REVISION_CONFLICT'}),{status:409});
      if(kind==='instruction'){purpose=payload.purpose;questions=payload.questions;}else{body=payload.body;category=payload.category;}
      revision++;
      return new Response(JSON.stringify(row(kind)));
    }
    return new Response(JSON.stringify({items:[row(kind)]}));
  });
});
afterEach(()=>{cleanup();vi.restoreAllMocks();});
function Root({kind,show=true,actor='teacher',session='session-a',owner=actor,manage=true}:{kind:'instruction'|'explanation';show?:boolean;actor?:string;session?:string;owner?:string;manage?:boolean}){
  return <ChatDraftSessionProvider><ChatDraftActor value={owner}>{show&&(kind==='instruction'
    ?<ReadingInstructions actorId={actor} sessionId={session} materials={materials} canManage={manage} onOpen={()=>{}}/>
    :<PageExplanations actorId={actor} sessionId={session} materials={materials} canManage={manage} onOpen={()=>{}} onPublish={async()=>{}}/>)}</ChatDraftActor></ChatDraftSessionProvider>;
}
async function edit(kind:'instruction'|'explanation'){
  fireEvent.click(await screen.findByRole('button',{name:kind==='instruction'?'Sửa chỉ dẫn':'Sửa bản nháp'}));
}
it('keeps the original instruction revision when its retained edit is reopened after a newer server read',async()=>{
  const view=render(<Root kind='instruction'/>);await edit('instruction');fireEvent.change(screen.getByLabelText('Mục đích'),{target:{value:'Private old-revision purpose'}});
  fireEvent.click(screen.getByRole('button',{name:'Hủy chỉnh sửa'}));revision=4;purpose='New server purpose';
  view.rerender(<Root kind='instruction' show={false}/>);view.rerender(<Root kind='instruction'/>);await edit('instruction');
  expect(screen.getByLabelText('Mục đích')).toHaveValue('Private old-revision purpose');fireEvent.click(screen.getByRole('button',{name:'Lưu chỉ dẫn'}));
  await waitFor(()=>expect(writes).toHaveLength(1));expect(writes[0].payload.revision).toBe(3);
  await screen.findByText('Dữ liệu đã thay đổi hoặc thao tác chưa hợp lệ. Hãy tải lại trạng thái.');expect(screen.getByLabelText('Mục đích')).toHaveValue('Private old-revision purpose');
});

it.each(['instruction','explanation'] as const)('keeps the %s draft when its fresh comparison read no longer exposes the record',async kind=>{
  render(<Root kind={kind}/>);await edit(kind);const field=kind==='instruction'?'Mục đích':'Nội dung lời giải';
  fireEvent.change(screen.getByLabelText(field),{target:{value:'Retained private prose'}});
  vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({items:[]})));
  fireEvent.click(screen.getByRole('button',{name:'Đối chiếu bản trên máy chủ'}));
  await screen.findByText(kind==='instruction'?'Không còn đọc được chỉ dẫn để đối chiếu. Nháp vẫn được giữ.':'Lời giải hoặc quyền đọc nguồn đã thay đổi. Nháp vẫn được giữ.');
  expect(screen.getByLabelText(field)).toHaveValue('Retained private prose');expect(screen.queryByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'})).toBeNull();expect(writes).toHaveLength(0);
});

it('does not rebase an explanation that has been published since editing began',async()=>{
  render(<Root kind='explanation'/>);await edit('explanation');fireEvent.change(screen.getByLabelText('Nội dung lời giải'),{target:{value:'Unsent editing prose'}});
  vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({items:[{...row('explanation'),status:'PUBLISHED',revision:4}]})));
  fireEvent.click(screen.getByRole('button',{name:'Đối chiếu bản trên máy chủ'}));await screen.findByText('Lời giải hoặc quyền đọc nguồn đã thay đổi. Nháp vẫn được giữ.');
  expect(screen.getByLabelText('Nội dung lời giải')).toHaveValue('Unsent editing prose');expect(writes).toHaveLength(0);
});

it.each(['instruction','explanation'] as const)('retries the exact uncertain %s edit with its original revision and key after reopening',async kind=>{
  const original=vi.mocked(fetch).getMockImplementation()!;
  const attempted:{payload:unknown;key:string|null}[]=[];
  vi.mocked(fetch).mockImplementation(async(input,init)=>{
    if(init?.method==='PATCH'){
      attempted.push({payload:JSON.parse(String(init.body)),key:new Headers(init.headers).get('Idempotency-Key')});
      if(attempted.length===1)throw new TypeError('Synthetic lost edit response');
    }
    return original(input,init);
  });
  const view=render(<Root kind={kind}/>);await edit(kind);const field=kind==='instruction'?'Mục đích':'Nội dung lời giải';
  fireEvent.change(screen.getByLabelText(field),{target:{value:'Uncertain retained edit'}});fireEvent.click(screen.getByRole('button',{name:kind==='instruction'?'Lưu chỉ dẫn':'Lưu bản nháp lời giải'}));
  await screen.findByText('Mất kết nối. Chưa xác định được kết quả; hãy tải lại trạng thái trước khi gửi lại.');
  revision=4;view.rerender(<Root kind={kind} show={false}/>);view.rerender(<Root kind={kind}/>);await screen.findByDisplayValue('Uncertain retained edit');
  fireEvent.click(screen.getByRole('button',{name:kind==='instruction'?'Lưu chỉ dẫn':'Lưu bản nháp lời giải'}));await waitFor(()=>expect(attempted).toHaveLength(2));
  expect(attempted[1]).toEqual(attempted[0]);expect(attempted[1].payload).toMatchObject({revision:3});
});

it.each(['instruction','explanation'] as const)('hides old server %s rows until the current role scope has completed a fresh authorized read',async kind=>{
  const view=render(<Root kind={kind}/>);await screen.findByText(kind==='instruction'?'Saved purpose':'Saved explanation');
  let finish!:(value:Response)=>void;
  vi.mocked(fetch).mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
  view.rerender(<Root kind={kind} owner='teacher-student-role' manage={false}/>);
  expect(screen.queryByText(kind==='instruction'?'Saved purpose':'Saved explanation')).toBeNull();
  await waitFor(()=>expect(finish).toBeTypeOf('function'));await act(async()=>finish(new Response(JSON.stringify({items:[]}))));
  expect(screen.queryByText(kind==='instruction'?'Saved purpose':'Saved explanation')).toBeNull();
});
it.each(['instruction','explanation'] as const)('requires an explicit %s conflict choice, preserves the earlier prose and saves the reviewed revision',async kind=>{
  const view=render(<Root kind={kind}/>);await edit(kind);
  const field=kind==='instruction'?'Mục đích':'Nội dung lời giải';
  fireEvent.change(screen.getByLabelText(field),{target:{value:'Private conflicting prose'}});
  revision=4;purpose='New server purpose';body='New server explanation';questions=['New server question'];category='ADD_EXAMPLE';
  fireEvent.click(screen.getByRole('button',{name:'Đối chiếu bản trên máy chủ'}));
  await screen.findByLabelText('Chọn nội dung: '+field);
  expect(screen.getByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'})).toBeDisabled();expect(writes).toHaveLength(0);
  fireEvent.change(screen.getByLabelText('Chọn nội dung: '+field),{target:{value:'mine'}});
  fireEvent.click(screen.getByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'}));
  expect(screen.getByLabelText(field)).toHaveValue('Private conflicting prose');
  expect(screen.getByLabelText(kind==='instruction'?'Câu hỏi tự kiểm tra mỗi dòng một câu':'Hành động')).toHaveValue(kind==='instruction'?'New server question':'ADD_EXAMPLE');
  view.rerender(<Root kind={kind} show={false}/>);view.rerender(<Root kind={kind}/>);await screen.findByText('Nháp trước khi đối chiếu (1)');
  expect(within(screen.getByRole('region',{name:'Nháp đã giữ 1',hidden:true})).getByText('Private conflicting prose')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:kind==='instruction'?'Lưu chỉ dẫn':'Lưu bản nháp lời giải'}));
  await waitFor(()=>expect(writes).toHaveLength(1));expect(writes[0].payload).toMatchObject({revision:4,...(kind==='instruction'?{purpose:'Private conflicting prose',questions:['New server question']}:{body:'Private conflicting prose',category:'ADD_EXAMPLE'})});
});
