import React from 'react';
import '@testing-library/jest-dom/vitest';
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {LearningWorkspace} from './LearningWorkspace';
import {LearningMetadataForm} from './LearningMetadataForm';
import {ChatDraftActor,ChatDraftSessionProvider,chatDraftActorScope} from '../chat/route-drafts';
const api=vi.hoisted(()=>({capabilities:vi.fn(),offerings:vi.fn(),sessions:vi.fn(),materials:vi.fn(),list:vi.fn(),request:vi.fn(),write:vi.fn()}));
vi.mock('../../lib/data/api/learning-gateway',()=>({LearningGateway:class{capabilities=api.capabilities;offerings=api.offerings;sessions=api.sessions;materials=api.materials;list=api.list;request=api.request;write=api.write;},LearningApiError:class extends Error{}}));
vi.mock('../../components/AppShell',()=>({AppShell:({children}:{children:React.ReactNode})=><ChatDraftActor value={chatDraftActorScope({user_id:'teacher',roles:['LECTURER']})}>{children}</ChatDraftActor>}));
vi.mock('./reader/LearningPdfReader',()=>({LearningPdfReader:()=>null}));
vi.mock('./ReadingInstructions',()=>({ReadingInstructions:()=>null}));
vi.mock('./LearningNotifications',()=>({LearningNotifications:()=>null}));
const offering='00000000-0000-4000-8000-000000000001';
const sessionA='00000000-0000-4000-8000-000000000002';
const sessionB='00000000-0000-4000-8000-000000000003';
const material='00000000-0000-4000-8000-000000000004';
let revision=3;
beforeEach(()=>{
  revision=3;vi.stubGlobal('BroadcastChannel',undefined);
  vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({user_id:'teacher',roles:['LECTURER']}))));
  api.capabilities.mockResolvedValue({available:true});api.offerings.mockResolvedValue([{id:offering,title:'Synthetic class',status:'ACTIVE',capabilities:{read:true,manage:true}}]);
  api.sessions.mockImplementation(async()=>[{id:sessionA,title:'Session A',description:'Saved A',sequence_no:1,revision,starts_at:null},{id:sessionB,title:'Session B',description:'Saved B',sequence_no:2,revision:1,starts_at:null}]);
  api.materials.mockResolvedValue([{id:material,offering_id:offering,title:'Synthetic material',description:'Saved description',revision:3,visibility:'VISIBLE',current_published_version_id:null,versions:[]}]);
  api.list.mockResolvedValue([]);api.request.mockResolvedValue({});
});
afterEach(()=>{cleanup();vi.resetAllMocks();vi.unstubAllGlobals();});
function Root({show=true}:{show?:boolean}){return <ChatDraftSessionProvider>{show&&<LearningWorkspace/>}</ChatDraftSessionProvider>;}
async function ready(){await screen.findByRole('heading',{name:'Session A'});await screen.findByRole('heading',{name:'Synthetic material'});screen.getByText('Chỉnh sửa buổi học').closest('details')!.open=true;screen.getByText('Chỉnh sửa thông tin học liệu').closest('details')!.open=true;}
it('restores independent session metadata when switching away and back',async()=>{
  render(<Root/>);await ready();
  fireEvent.change(screen.getByLabelText('Tiêu đề buổi'),{target:{value:'Unsent A title'}});
  fireEvent.change(screen.getByLabelText('Mô tả buổi'),{target:{value:'Unsent A description'}});
  fireEvent.click(screen.getByRole('button',{name:'2. Session B'}));await screen.findByRole('heading',{name:'Session B'});
  fireEvent.change(screen.getByLabelText('Tiêu đề buổi'),{target:{value:'Unsent B title'}});
  fireEvent.click(screen.getByRole('button',{name:'1. Session A'}));await screen.findByRole('heading',{name:'Session A'});
  expect(screen.getByLabelText('Tiêu đề buổi')).toHaveValue('Unsent A title');expect(screen.getByLabelText('Mô tả buổi')).toHaveValue('Unsent A description');
});
it('retains new-session and material metadata through route unmount',async()=>{
  const view=render(<Root/>);await ready();
  fireEvent.change(screen.getByLabelText('Tên buổi mới'),{target:{value:'Unsent new session'}});
  fireEvent.change(screen.getByLabelText('Mô tả'),{target:{value:'Unsent material description'}});
  view.rerender(<Root show={false}/>);view.rerender(<Root/>);await ready();
  expect(screen.getByLabelText('Tên buổi mới')).toHaveValue('Unsent new session');expect(screen.getByLabelText('Mô tả')).toHaveValue('Unsent material description');
});
it('previews a retained edit using its original revision after a newer read',async()=>{
  api.write.mockResolvedValue({preview_id:'preview',confirmation_token:'token',expires_at:'2099-01-01T00:00:00Z',payload:{}});
  const view=render(<Root/>);await ready();fireEvent.change(screen.getByLabelText('Tiêu đề buổi'),{target:{value:'Edit based on revision three'}});
  view.rerender(<Root show={false}/>);revision=4;view.rerender(<Root/>);await ready();
  fireEvent.click(screen.getByRole('button',{name:'Xem trước cập nhật'}));await waitFor(()=>expect(api.write).toHaveBeenCalled());
  const body=api.write.mock.calls.find(call=>call[0]==='/action-previews')?.[1];expect(body.payload.revision).toBe(3);expect(body.payload.title).toBe('Edit based on revision three');
  expect(screen.getByRole('dialog',{name:'Cập nhật buổi học'})).toHaveTextContent('Cập nhật tiêu đề, mô tả hoặc thời gian buổi học theo thông tin đã xem trước.');
});
it('unlocks the original draft after an unconfirmed preview is unmounted',async()=>{
  api.write.mockResolvedValue({preview_id:'preview',confirmation_token:'token',expires_at:'2099-01-01T00:00:00Z',payload:{}});
  const view=render(<Root/>);await ready();fireEvent.change(screen.getByLabelText('Tiêu đề buổi'),{target:{value:'Unconfirmed retained title'}});
  fireEvent.click(screen.getByRole('button',{name:'Xem trước cập nhật'}));await screen.findByRole('dialog',{name:'Cập nhật buổi học'});
  view.rerender(<Root show={false}/>);view.rerender(<Root/>);await ready();
  await waitFor(()=>expect(screen.getByLabelText('Tiêu đề buổi')).toBeEnabled());
  expect(screen.getByLabelText('Tiêu đề buổi')).toHaveValue('Unconfirmed retained title');
  expect(screen.queryByRole('dialog')).toBeNull();expect(api.write.mock.calls.every(call=>call[0]==='/action-previews')).toBe(true);
});
it('retains the exact create payload and key after uncertain failure despite a newer session list',async()=>{
  api.write.mockRejectedValue(new Error('Synthetic uncertain create'));
  const view=render(<Root/>);await ready();fireEvent.change(screen.getByLabelText('Tên buổi mới'),{target:{value:'Pending create'}});
  fireEvent.click(screen.getByRole('button',{name:'Thêm buổi'}));await screen.findByText('Synthetic uncertain create');
  const first=api.write.mock.calls[0];expect(first[1].sequence_no).toBe(3);
  view.rerender(<Root show={false}/>);
  api.sessions.mockResolvedValue([{id:sessionA,title:'Session A',description:'Saved A',sequence_no:1,revision:3},{id:sessionB,title:'Session B',sequence_no:2,revision:1},{id:'created-session',title:'Pending create',sequence_no:3,revision:1}]);
  view.rerender(<Root/>);await ready();fireEvent.click(screen.getByRole('button',{name:'Thêm buổi'}));await waitFor(()=>expect(api.write).toHaveBeenCalledTimes(2));
  expect(api.write.mock.calls[1]).toEqual(first);
});
it('keeps a confirmed write pending through unmount and applies its acknowledgement once',async()=>{
  let finish!:(value:unknown)=>void;
  api.write.mockImplementation(async(path:string)=>path==='/action-previews'?{preview_id:'preview',confirmation_token:'token',expires_at:'2099-01-01T00:00:00Z',payload:{}}:new Promise(resolve=>{finish=resolve;}));
  const view=render(<Root/>);await ready();fireEvent.change(screen.getByLabelText('Tiêu đề buổi'),{target:{value:'Confirmed original title'}});
  fireEvent.click(screen.getByRole('button',{name:'Xem trước cập nhật'}));await screen.findByRole('dialog',{name:'Cập nhật buổi học'});
  fireEvent.click(screen.getByRole('checkbox',{name:'Tôi đã kiểm tra thông tin và tác động.'}));fireEvent.click(screen.getByRole('button',{name:'Xác nhận thay đổi'}));
  await waitFor(()=>expect(finish).toBeTypeOf('function'));
  view.rerender(<Root show={false}/>);view.rerender(<Root/>);await ready();expect(screen.getByLabelText('Tiêu đề buổi')).toBeDisabled();
  await act(async()=>finish({}));await waitFor(()=>expect(screen.getByLabelText('Tiêu đề buổi')).toBeEnabled());
  expect(api.write.mock.calls.filter(call=>call[0]!== '/action-previews')).toHaveLength(1);
});
function Editor({actor='teacher',roles=['LECTURER'],save=async()=>{}}:{actor?:string;roles?:string[];save?:(payload:Record<string,unknown>,key:string)=>Promise<unknown>}){
  return <ChatDraftActor value={chatDraftActorScope({user_id:actor,roles})}><LearningMetadataForm actorId={actor} draftId='same-record' initialValues={{title:''}} basis={{revision:3}}
    toPayload={({values,basis})=>({...values,revision:basis.revision})} onSave={save}>{(values,change)=><><label>Private title<input value={values.title} onChange={event=>change('title',event.target.value)}/></label><button>Save synthetic metadata</button></>}</LearningMetadataForm></ChatDraftActor>;
}
it('separates metadata drafts by verified account and role scope',async()=>{
  const view=render(<ChatDraftSessionProvider><Editor/></ChatDraftSessionProvider>);
  fireEvent.change(screen.getByLabelText('Private title'),{target:{value:'Private original account title'}});
  view.rerender(<ChatDraftSessionProvider><Editor actor='teacher-b'/></ChatDraftSessionProvider>);expect(screen.getByLabelText('Private title')).toHaveValue('');
  view.rerender(<ChatDraftSessionProvider><Editor roles={['STUDENT']}/></ChatDraftSessionProvider>);expect(screen.getByLabelText('Private title')).toHaveValue('');
  view.rerender(<ChatDraftSessionProvider><Editor/></ChatDraftSessionProvider>);expect(screen.getByLabelText('Private title')).toHaveValue('Private original account title');
});
it('applies a late acknowledgement only to the initiating owner draft',async()=>{
  let finish!:(value:unknown)=>void;const save=vi.fn(()=>new Promise(resolve=>{finish=resolve;}));
  const view=render(<ChatDraftSessionProvider><Editor save={save}/></ChatDraftSessionProvider>);
  fireEvent.change(screen.getByLabelText('Private title'),{target:{value:'Owner A submitted title'}});fireEvent.click(screen.getByRole('button',{name:'Save synthetic metadata'}));
  await waitFor(()=>expect(finish).toBeTypeOf('function'));
  view.rerender(<ChatDraftSessionProvider><Editor actor='teacher-b' save={save}/></ChatDraftSessionProvider>);
  fireEvent.change(screen.getByLabelText('Private title'),{target:{value:'Owner B unsent title'}});await act(async()=>finish({}));
  expect(screen.getByLabelText('Private title')).toHaveValue('Owner B unsent title');expect(save).toHaveBeenCalledTimes(1);
  view.rerender(<ChatDraftSessionProvider><Editor save={save}/></ChatDraftSessionProvider>);expect(screen.getByLabelText('Private title')).toHaveValue('');
});
it('keeps the initiating session context when a preview arrives after switching sessions',async()=>{
  let finish!:(value:unknown)=>void;
  api.write.mockImplementation(async(path:string)=>path==='/action-previews'?new Promise(resolve=>{finish=resolve;}):{});
  render(<Root/>);await ready();fireEvent.change(screen.getByLabelText('Tiêu đề buổi'),{target:{value:'Session A proposed title'}});
  fireEvent.click(screen.getByRole('button',{name:'Xem trước cập nhật'}));await waitFor(()=>expect(finish).toBeTypeOf('function'));
  fireEvent.click(screen.getByRole('button',{name:'2. Session B'}));await screen.findByRole('heading',{name:'Session B'});
  await act(async()=>finish({preview_id:'preview',confirmation_token:'token',expires_at:'2099-01-01T00:00:00Z',payload:{}}));
  const dialog=await screen.findByRole('dialog',{name:'Cập nhật buổi học'});expect(dialog).toHaveTextContent('Buổi: Session A.');expect(dialog).not.toHaveTextContent('Buổi: Session B.');
  fireEvent.click(screen.getByRole('checkbox',{name:'Tôi đã kiểm tra thông tin và tác động.'}));fireEvent.click(screen.getByRole('button',{name:'Xác nhận thay đổi'}));
  await waitFor(()=>expect(api.write.mock.calls.some(call=>call[0]===`/sessions/${sessionA}`)).toBe(true));
  expect(api.write.mock.calls.some(call=>call[0]===`/sessions/${sessionB}`)).toBe(false);
});

it('compares fresh session fields without writing and explicitly rebases only after review',async()=>{
  api.write.mockResolvedValue({preview_id:'preview',confirmation_token:'token',expires_at:'2099-01-01T00:00:00Z',payload:{}});
  render(<Root/>);await ready();
  fireEvent.change(screen.getByLabelText('Tiêu đề buổi'),{target:{value:'My session title'}});
  api.sessions.mockResolvedValue([{id:sessionA,title:'Session A',description:'New server description',sequence_no:1,revision:4,starts_at:null}]);
  const form=screen.getByLabelText('Tiêu đề buổi').closest('form')!;
  fireEvent.click(within(form).getByRole('button',{name:'Đối chiếu bản trên máy chủ'}));
  await within(form).findByText('New server description');
  expect(screen.getByLabelText('Mô tả buổi')).toHaveValue('Saved A');expect(api.write).not.toHaveBeenCalled();
  fireEvent.click(within(form).getByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'}));
  expect(screen.getByLabelText('Tiêu đề buổi')).toHaveValue('My session title');expect(screen.getByLabelText('Mô tả buổi')).toHaveValue('New server description');
  expect(within(form).getByText('Nháp trước khi đối chiếu (1)')).toBeInTheDocument();expect(api.write).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button',{name:'Xem trước cập nhật'}));await screen.findByRole('dialog');
  expect(api.write.mock.calls[0][1].payload).toMatchObject({title:'My session title',description:'New server description',revision:4});
});

it('requires a deliberate choice for a concurrently changed material field and keeps the old draft',async()=>{
  api.write.mockResolvedValue({preview_id:'preview',confirmation_token:'token',expires_at:'2099-01-01T00:00:00Z',payload:{}});
  const view=render(<Root/>);await ready();fireEvent.change(screen.getByLabelText('Mô tả'),{target:{value:'My material description'}});
  api.materials.mockResolvedValue([{id:material,offering_id:offering,title:'Server material title',description:'Server material description',revision:4,visibility:'VISIBLE',versions:[]}]);
  const form=screen.getByLabelText('Mô tả').closest('form')!;
  fireEvent.click(within(form).getByRole('button',{name:'Đối chiếu bản trên máy chủ'}));await within(form).findByText('Server material description');
  expect(within(form).getByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'})).toBeDisabled();
  fireEvent.change(within(form).getByLabelText('Chọn nội dung: Mô tả'),{target:{value:'mine'}});
  fireEvent.click(within(form).getByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'}));
  view.rerender(<Root show={false}/>);view.rerender(<Root/>);await screen.findByRole('heading',{name:'Server material title'});
  screen.getByText('Chỉnh sửa thông tin học liệu').closest('details')!.open=true;
  expect(screen.getByLabelText('Mô tả')).toHaveValue('My material description');expect(screen.getByLabelText('Tiêu đề')).toHaveValue('Server material title');
  expect(screen.getByText('Nháp trước khi đối chiếu (1)')).toBeInTheDocument();expect(api.write).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button',{name:'Xem trước thay đổi'}));await screen.findByRole('dialog');
  expect(api.write.mock.calls[0][1].payload).toMatchObject({title:'Server material title',description:'My material description',revision:4});
});
