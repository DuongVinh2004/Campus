import React from 'react';
import '@testing-library/jest-dom/vitest';
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {VersionChangeEditor} from './VersionChanges';
import {ChatDraftActor,ChatDraftSessionProvider,chatDraftActorScope} from '../chat/route-drafts';
import type {LearningMaterial,LearningVersionChangeSet} from '../../lib/data/api/learning-gateway';
const material:LearningMaterial={id:'material',offering_id:'offering',title:'Synthetic',description:'',visibility:'VISIBLE',revision:1,current_published_version_id:'base',versions:[
  {id:'base',version_no:1,processing_state:'READY',publication_state:'PUBLISHED',page_count:3,has_text_layer:true,revision:1},
  {id:'target',version_no:2,processing_state:'READY',publication_state:'DRAFT',page_count:4,has_text_layer:true,revision:1}]};
const row:LearningVersionChangeSet={revision:3,mode:'WHOLE_DOCUMENT',target_version_id:'target',target_version_no:2,target_media_type:'application/pdf',target_guidance:'Saved guidance',base_available:true,base_version_id:'base',base_version_no:1,reason:'Saved reason',items:[]};
let denied=false;
beforeEach(()=>{denied=false;vi.spyOn(globalThis,'fetch').mockImplementation(async()=>new Response(JSON.stringify(denied?{code:'FORBIDDEN',detail:'Synthetic denial'}:{change_set:row}),{status:denied?403:200}));});
afterEach(()=>{cleanup();vi.restoreAllMocks();});
function Root({show=true,actor='teacher',save=async()=>row}:{show?:boolean;actor?:string;save?:(payload:Record<string,unknown>,key:string)=>Promise<LearningVersionChangeSet>}){
  return <ChatDraftSessionProvider><ChatDraftActor value={chatDraftActorScope({user_id:actor,roles:['LECTURER']})}>
    {show&&<VersionChangeEditor actorId={actor} version={material.versions[1]} material={material} onSave={save}/>}
  </ChatDraftActor></ChatDraftSessionProvider>;
}
async function openEditor(){
  const summary=screen.getByText('Mô tả thay đổi giữa hai bản');
  const details=summary.closest('details')!;
  details.open=true;fireEvent(details,new Event('toggle'));
  await screen.findByLabelText('Lý do cập nhật');
}
it('keeps source, reason, guidance and page-map prose through route unmount',async()=>{
  const view=render(<Root/>);await openEditor();
  fireEvent.change(screen.getByLabelText('Lý do cập nhật'),{target:{value:'Unsent reason'}});
  fireEvent.change(screen.getByLabelText('Chỉ dẫn đọc độc lập của bản mới'),{target:{value:'Unsent guidance'}});
  fireEvent.change(screen.getByLabelText('Phạm vi thay đổi'),{target:{value:'PAGE_MAP'}});
  fireEvent.click(screen.getByRole('button',{name:'Thêm thay đổi'}));
  fireEvent.change(screen.getByLabelText('Mô tả so sánh'),{target:{value:'Unsent page comparison'}});
  view.rerender(<Root show={false}/>);view.rerender(<Root/>);await openEditor();
  expect(screen.getByLabelText('Lý do cập nhật')).toHaveValue('Unsent reason');
  expect(screen.getByLabelText('Chỉ dẫn đọc độc lập của bản mới')).toHaveValue('Unsent guidance');
  expect(screen.getByLabelText('Mô tả so sánh')).toHaveValue('Unsent page comparison');
});
it('separates accounts and restores the original account draft',async()=>{
  const view=render(<Root/>);await openEditor();
  fireEvent.change(screen.getByLabelText('Lý do cập nhật'),{target:{value:'Teacher A private'}});
  view.rerender(<Root actor='teacher-b'/>);await openEditor();
  expect(screen.getByLabelText('Lý do cập nhật')).toHaveValue('Saved reason');
  view.rerender(<Root/>);await openEditor();
  expect(screen.getByLabelText('Lý do cập nhật')).toHaveValue('Teacher A private');
});
it('preserves a pending operation key after failed save and unmount',async()=>{
  const save=vi.fn(async()=>{throw new Error('Synthetic uncertain response');});
  const view=render(<Root save={save}/>);await openEditor();
  fireEvent.change(screen.getByLabelText('Lý do cập nhật'),{target:{value:'Pending reason'}});
  fireEvent.click(screen.getByRole('button',{name:'Lưu mô tả thay đổi'}));await screen.findByRole('alert');
  view.rerender(<Root show={false} save={save}/>);view.rerender(<Root save={save}/>);await openEditor();
  fireEvent.click(screen.getByRole('button',{name:'Lưu mô tả thay đổi'}));await waitFor(()=>expect(save).toHaveBeenCalledTimes(2));
  expect(save.mock.calls[1]).toEqual(save.mock.calls[0]);
});
it('waits for the original save through unmount and keeps its acknowledged revision',async()=>{
  let finish!:(value:LearningVersionChangeSet)=>void;
  const save=vi.fn((_payload:Record<string,unknown>,_key:string)=>new Promise<LearningVersionChangeSet>(resolve=>{finish=resolve;}));
  const view=render(<Root save={save}/>);await openEditor();
  fireEvent.change(screen.getByLabelText('Lý do cập nhật'),{target:{value:'Original pending reason'}});
  fireEvent.click(screen.getByRole('button',{name:'Lưu mô tả thay đổi'}));
  view.rerender(<Root show={false} save={save}/>);view.rerender(<Root save={save}/>);await openEditor();
  expect(screen.getByLabelText('Lý do cập nhật')).toBeDisabled();expect(save).toHaveBeenCalledTimes(1);
  await act(async()=>finish({...row,revision:4}));
  expect(screen.getByLabelText('Lý do cập nhật')).toBeEnabled();
  expect(screen.getByLabelText('Lý do cập nhật')).toHaveValue('Original pending reason');
  fireEvent.change(screen.getByLabelText('Lý do cập nhật'),{target:{value:'Next revision reason'}});
  fireEvent.click(screen.getByRole('button',{name:'Lưu mô tả thay đổi'}));
  expect(save.mock.calls[1][0].revision).toBe(4);expect(save.mock.calls[1][1]).not.toBe(save.mock.calls[0][1]);
});
it('conceals denied drafts without discarding them when access returns',async()=>{
  const view=render(<Root/>);await openEditor();
  fireEvent.change(screen.getByLabelText('Lý do cập nhật'),{target:{value:'Retained after denied read'}});
  view.rerender(<Root show={false}/>);denied=true;view.rerender(<Root/>);
  await screen.findByRole('alert');expect(screen.queryByLabelText('Lý do cập nhật')).toBeNull();
  view.rerender(<Root show={false}/>);denied=false;view.rerender(<Root/>);await openEditor();
  expect(screen.getByLabelText('Lý do cập nhật')).toHaveValue('Retained after denied read');
});
it('keeps the original revision after a newer server description appears',async()=>{
  const save=vi.fn(async(_payload:Record<string,unknown>,_key:string)=>{throw new Error('Synthetic revision conflict');});
  const view=render(<Root save={save}/>);await openEditor();
  fireEvent.change(screen.getByLabelText('Lý do cập nhật'),{target:{value:'Private original revision three'}});
  view.rerender(<Root show={false} save={save}/>);
  vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({change_set:{...row,revision:4,reason:'Other writer revision four'}})));
  view.rerender(<Root save={save}/>);await openEditor();
  fireEvent.click(screen.getByRole('button',{name:'Lưu mô tả thay đổi'}));await screen.findByRole('alert');
  expect(save.mock.calls[0][0].revision).toBe(3);expect(screen.getByLabelText('Lý do cập nhật')).toHaveValue('Private original revision three');
});

it('compares the base, mode and page map as one group and preserves independent server guidance',async()=>{
  const save=vi.fn(async(_payload:Record<string,unknown>,_key:string)=>({...row,revision:5}));render(<Root save={save}/>);await openEditor();
  fireEvent.change(screen.getByLabelText('Lý do cập nhật'),{target:{value:'My reason'}});
  fireEvent.change(screen.getByLabelText('Phạm vi thay đổi'),{target:{value:'PAGE_MAP'}});fireEvent.click(screen.getByRole('button',{name:'Thêm thay đổi'}));
  fireEvent.change(screen.getByLabelText('Mô tả so sánh'),{target:{value:'My original page mapping'}});
  fireEvent.change(screen.getByLabelText('Bản trước · Trang PDF'),{target:{value:'1'}});fireEvent.change(screen.getByLabelText('Bản mới · Trang PDF'),{target:{value:'2'}});
  vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({change_set:{...row,revision:4,mode:'UNSPECIFIED',target_guidance:'New server guidance'}})));
  fireEvent.click(screen.getByRole('button',{name:'Đối chiếu bản trên máy chủ'}));await screen.findByLabelText('Chọn nội dung: Cấu trúc so sánh');
  expect(screen.getByRole('region',{name:'Đối chiếu: Cấu trúc so sánh'})).toHaveTextContent('My original page mapping');
  expect(screen.getByRole('region',{name:'Đối chiếu: Cấu trúc so sánh'})).not.toHaveTextContent('"base_version_id"');
  expect(screen.getByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'})).toBeDisabled();expect(save).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Chọn nội dung: Cấu trúc so sánh'),{target:{value:'mine'}});
  fireEvent.click(screen.getByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'}));
  expect(screen.getByLabelText('Mô tả so sánh')).toHaveValue('My original page mapping');expect(screen.getByLabelText('Chỉ dẫn đọc độc lập của bản mới')).toHaveValue('New server guidance');
  fireEvent.click(screen.getByRole('button',{name:'Lưu mô tả thay đổi'}));await waitFor(()=>expect(save).toHaveBeenCalled());
  expect(save.mock.calls[0][0]).toMatchObject({revision:4,base_version_id:'base',mode:'PAGE_MAP',reason:'My reason',target_guidance:'New server guidance',items:[{old_page:1,new_page:2,description:'My original page mapping'}]});
});

it('refuses to rebase against a description whose previous source has become unavailable',async()=>{
  render(<Root/>);await openEditor();fireEvent.change(screen.getByLabelText('Lý do cập nhật'),{target:{value:'Keep my reason'}});
  vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({change_set:{...row,revision:4,base_available:false,mode:'UNSPECIFIED',items:[]}})));
  fireEvent.click(screen.getByRole('button',{name:'Đối chiếu bản trên máy chủ'}));await screen.findByText('Bản trước không còn đủ điều kiện để đối chiếu. Nháp vẫn được giữ.');
  expect(screen.getByLabelText('Lý do cập nhật')).toHaveValue('Keep my reason');expect(screen.queryByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'})).toBeNull();
});

it('keeps a newer local edit on its own baseline when the previous save acknowledgement arrives',async()=>{
  let finish!:(value:LearningVersionChangeSet)=>void;
  const save=vi.fn((_payload:Record<string,unknown>,_key:string)=>new Promise<LearningVersionChangeSet>(resolve=>{finish=resolve;}));
  const view=render(<Root save={save}/>);await openEditor();fireEvent.change(screen.getByLabelText('Lý do cập nhật'),{target:{value:'Submitted earlier reason'}});
  fireEvent.click(screen.getByRole('button',{name:'Lưu mô tả thay đổi'}));
  view.rerender(<Root show={false} save={save}/>);view.rerender(<Root save={save}/>);await openEditor();
  fireEvent.change(screen.getByLabelText('Lý do cập nhật'),{target:{value:'Newer retained local reason'}});
  await act(async()=>finish({...row,revision:4}));expect(screen.getByLabelText('Lý do cập nhật')).toHaveValue('Newer retained local reason');
  fireEvent.click(screen.getByRole('button',{name:'Lưu mô tả thay đổi'}));expect(save.mock.calls[1][0].revision).toBe(3);
});

it('keeps its exact retry key when an acknowledgement does not advance the submitted revision',async()=>{
  const save=vi.fn(async(_payload:Record<string,unknown>,_key:string)=>row);render(<Root save={save}/>);await openEditor();
  fireEvent.change(screen.getByLabelText('Lý do cập nhật'),{target:{value:'Retain invalid-ack draft'}});fireEvent.click(screen.getByRole('button',{name:'Lưu mô tả thay đổi'}));
  await screen.findByText('Chưa xác nhận được phiên bản đã lưu. Nháp và khóa thử lại vẫn được giữ.');
  fireEvent.click(screen.getByRole('button',{name:'Lưu mô tả thay đổi'}));await waitFor(()=>expect(save).toHaveBeenCalledTimes(2));expect(save.mock.calls[1]).toEqual(save.mock.calls[0]);
});

it('compares a draft created before another writer created the first server description',async()=>{
  vi.mocked(fetch).mockImplementation(async()=>new Response(JSON.stringify({change_set:null})));
  const save=vi.fn(async(_payload:Record<string,unknown>,_key:string)=>({...row,revision:2}));render(<Root save={save}/>);await openEditor();
  fireEvent.change(screen.getByLabelText('Phạm vi thay đổi'),{target:{value:'WHOLE_DOCUMENT'}});fireEvent.change(screen.getByLabelText('Lý do cập nhật'),{target:{value:'My creation reason'}});
  vi.mocked(fetch).mockImplementation(async()=>new Response(JSON.stringify({change_set:{...row,revision:1}})));
  fireEvent.click(screen.getByRole('button',{name:'Đối chiếu bản trên máy chủ'}));await screen.findByLabelText('Chọn nội dung: Lý do cập nhật');
  fireEvent.change(screen.getByLabelText('Chọn nội dung: Lý do cập nhật'),{target:{value:'mine'}});fireEvent.click(screen.getByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'}));
  fireEvent.click(screen.getByRole('button',{name:'Lưu mô tả thay đổi'}));await waitFor(()=>expect(save).toHaveBeenCalled());expect(save.mock.calls[0][0]).toMatchObject({revision:1,reason:'My creation reason',target_guidance:'Saved guidance'});
});
