import React from 'react';
import '@testing-library/jest-dom/vitest';
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {LearningWorkspace} from './LearningWorkspace';
import {LearningApiError} from '../../lib/data/api/learning-gateway';
import {ChatDraftActor,ChatDraftSessionProvider,chatDraftActorScope} from '../chat/route-drafts';
const api=vi.hoisted(()=>({capabilities:vi.fn(),offerings:vi.fn(),sessions:vi.fn(),materials:vi.fn(),list:vi.fn(),request:vi.fn(),write:vi.fn(),upload:vi.fn(),preview:vi.fn()}));
vi.mock('../../lib/data/api/learning-gateway',()=>({LearningGateway:class{capabilities=api.capabilities;offerings=api.offerings;sessions=api.sessions;materials=api.materials;list=api.list;request=api.request;write=api.write;upload=api.upload;preview=api.preview;},LearningApiError:class extends Error{constructor(public status:number,public code:string,message:string){super(message);}}}));
vi.mock('../../components/AppShell',()=>({AppShell:({children}:{children:React.ReactNode})=><ChatDraftActor value={chatDraftActorScope({user_id:'teacher',roles:['LECTURER']})}>{children}</ChatDraftActor>}));
vi.mock('./ReadingInstructions',()=>({ReadingInstructions:()=>null}));vi.mock('./LearningNotifications',()=>({LearningNotifications:()=>null}));vi.mock('./reader/LearningPdfReader',()=>({LearningPdfReader:()=>null}));
const material='00000000-0000-4000-8000-000000000001',version='00000000-0000-4000-8000-000000000002';
beforeEach(()=>{
  vi.stubGlobal('BroadcastChannel',undefined);vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({user_id:'teacher',roles:['LECTURER']}))));
  api.capabilities.mockResolvedValue({available:true});api.offerings.mockResolvedValue([{id:'offering',title:'Synthetic class',status:'ACTIVE',capabilities:{read:true,manage:true}}]);
  api.sessions.mockResolvedValue([{id:'session',title:'Synthetic session',sequence_no:1,revision:1}]);
  api.materials.mockResolvedValue([{id:material,title:'Synthetic material',description:'',visibility:'VISIBLE',revision:1,current_published_version_id:null,versions:[{id:version,version_no:1,processing_state:'READY',publication_state:'DRAFT'}]}]);
  api.list.mockResolvedValue([]);api.request.mockResolvedValue({});api.upload.mockResolvedValue({id:version,version_no:1,processing_state:'READY'});
});
afterEach(()=>{cleanup();vi.resetAllMocks();vi.unstubAllGlobals();});
function Root({show=true}:{show?:boolean}){return <ChatDraftSessionProvider>{show&&<LearningWorkspace/>}</ChatDraftSessionProvider>;}
async function ready(){await screen.findByRole('heading',{name:'Synthetic material'});}
it('uses the same selected File after actual route unmount without another file picker',async()=>{
  const view=render(<Root/>);await ready();screen.getByText('Tải phiên bản mới').closest('details')!.open=true;
  const file=new File(['synthetic'],'retained.pdf',{type:'application/pdf'});fireEvent.change(screen.getAllByLabelText('File PDF')[0],{target:{files:[file]}});
  view.rerender(<Root show={false}/>);view.rerender(<Root/>);await ready();screen.getByText('Tải phiên bản mới').closest('details')!.open=true;
  fireEvent.click(screen.getByRole('button',{name:'Tải phiên bản'}));await waitFor(()=>expect(api.upload).toHaveBeenCalled());expect(api.upload.mock.calls[0][1]).toBe(file);
});
it('retains the scheduled class-local publication time across route unmount',async()=>{
  const view=render(<Root/>);await ready();fireEvent.change(screen.getByLabelText('Hẹn giờ công bố'),{target:{value:'2030-11-01T15:00'}});
  view.rerender(<Root show={false}/>);view.rerender(<Root/>);await ready();expect(screen.getByLabelText('Hẹn giờ công bố')).toHaveValue('2030-11-01T15:00');
});
it('does not clear a scheduled time when its preview is returned without publication',async()=>{
  api.preview.mockResolvedValue({preview_id:'preview',confirmation_token:'token',expires_at:'2099-01-01T00:00:00Z'});
  render(<Root/>);await ready();screen.getByText('Lịch sử phiên bản').closest('details')!.open=true;
  fireEvent.change(screen.getByLabelText('Hẹn giờ công bố'),{target:{value:'2030-11-01T15:00'}});fireEvent.click(screen.getByRole('button',{name:'Xem trước lịch'}));
  await screen.findByRole('dialog',{name:'Xác nhận công bố học liệu'});expect(screen.getByRole('button',{name:'Xác nhận'})).toBeDisabled();
  fireEvent.click(screen.getByRole('button',{name:'Quay lại'}));expect(screen.getByLabelText('Hẹn giờ công bố')).toHaveValue('2030-11-01T15:00');
  expect(api.preview.mock.calls[0].slice(0,3)).toEqual([version,'publish','2030-11-01T08:00:00.000Z']);expect(api.write).not.toHaveBeenCalled();
});
it('retains an acknowledged new material target across an uncertain upload and route remount',async()=>{
  api.write.mockResolvedValue({id:material});api.upload.mockRejectedValueOnce(new Error('Synthetic uncertain upload')).mockResolvedValueOnce({id:version,version_no:1});
  const view=render(<Root/>);await ready();screen.getByText('Thêm bài giảng PDF').closest('details')!.open=true;
  fireEvent.change(screen.getByLabelText('Tiêu đề bài giảng'),{target:{value:'Unsent new material'}});
  const file=new File(['synthetic'],'new-material.pdf');fireEvent.change(screen.getAllByLabelText('File PDF')[1],{target:{files:[file]}});
  fireEvent.click(screen.getByRole('button',{name:'Tải và lưu nháp'}));await screen.findByText('Synthetic uncertain upload');
  view.rerender(<Root show={false}/>);view.rerender(<Root/>);await ready();screen.getByText('Thêm bài giảng PDF').closest('details')!.open=true;
  expect(screen.getByLabelText('Tiêu đề bài giảng')).toBeDisabled();fireEvent.click(screen.getByRole('button',{name:'Kiểm tra và tiếp tục tải'}));
  await waitFor(()=>expect(api.upload).toHaveBeenCalledTimes(2));expect(api.write).toHaveBeenCalledTimes(1);expect(api.upload.mock.calls[1][0]).toBe(material);expect(api.upload.mock.calls[1][1]).toBe(file);expect(api.upload.mock.calls[1][4]).toBe(api.upload.mock.calls[0][4]);
});
it('waits for the original transfer through route unmount without submitting it again',async()=>{
  let finish!:(value:unknown)=>void;api.upload.mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
  const view=render(<Root/>);await ready();screen.getByText('Tải phiên bản mới').closest('details')!.open=true;
  const file=new File(['synthetic'],'pending.pdf');const input=screen.getAllByLabelText('File PDF')[0] as HTMLInputElement;
  act(()=>{fireEvent.change(input,{target:{files:[file]}});fireEvent.submit(input.form!);fireEvent.submit(input.form!);});await waitFor(()=>expect(finish).toBeTypeOf('function'));
  view.rerender(<Root show={false}/>);view.rerender(<Root/>);await ready();screen.getByText('Tải phiên bản mới').closest('details')!.open=true;
  expect(screen.getAllByLabelText('File PDF')[0]).toBeDisabled();expect(api.upload).toHaveBeenCalledTimes(1);
  await act(async()=>finish({id:version,version_no:1}));await waitFor(()=>expect(screen.getAllByLabelText('File PDF')[0]).toBeEnabled());
  expect(screen.queryByText(/Tệp đang giữ trong tab: pending.pdf/)).toBeNull();expect(api.upload).toHaveBeenCalledTimes(1);
});

it('keeps both a title and File selected in one event batch before immediate submission',async()=>{
  api.write.mockResolvedValue({id:material});render(<Root/>);await ready();screen.getByText('Thêm bài giảng PDF').closest('details')!.open=true;
  const input=screen.getAllByLabelText('File PDF')[1] as HTMLInputElement;const file=new File(['synthetic'],'batched-selection.pdf');
  act(()=>{fireEvent.change(screen.getByLabelText('Tiêu đề bài giảng'),{target:{value:'Retain this batched title'}});fireEvent.change(input,{target:{files:[file]}});fireEvent.submit(input.form!);});
  await waitFor(()=>expect(api.upload).toHaveBeenCalled());expect(api.write.mock.calls[0][1].title).toBe('Retain this batched title');expect(api.upload.mock.calls[0][1]).toBe(file);
});
it('restarts only a verified stopped transfer while preserving its created material and title',async()=>{
  api.write.mockResolvedValue({id:material});api.upload.mockRejectedValueOnce(new LearningApiError(409,'UPLOAD_ABORTED','Stopped synthetic transfer')).mockResolvedValueOnce({id:version,version_no:1});
  render(<Root/>);await ready();screen.getByText('Thêm bài giảng PDF').closest('details')!.open=true;
  fireEvent.change(screen.getByLabelText('Tiêu đề bài giảng'),{target:{value:'Original created title'}});
  fireEvent.change(screen.getAllByLabelText('File PDF')[1],{target:{files:[new File(['one'],'first.pdf')]}});
  fireEvent.click(screen.getByRole('button',{name:'Tải và lưu nháp'}));fireEvent.click(await screen.findByRole('button',{name:'Bắt đầu lượt tải mới'}));
  expect(screen.getByLabelText('Tiêu đề bài giảng')).toBeDisabled();expect(screen.getByLabelText('Tiêu đề bài giảng')).toHaveValue('Original created title');expect(screen.getAllByLabelText('File PDF')[1]).toBeEnabled();
  const replacement=new File(['two'],'second.pdf');fireEvent.change(screen.getAllByLabelText('File PDF')[1],{target:{files:[replacement]}});
  fireEvent.click(screen.getByRole('button',{name:'Tải và lưu nháp'}));await waitFor(()=>expect(api.upload).toHaveBeenCalledTimes(2));
  expect(api.write).toHaveBeenCalledTimes(1);expect(api.upload.mock.calls[1][0]).toBe(material);expect(api.upload.mock.calls[1][1]).toBe(replacement);expect(api.upload.mock.calls[1][4]).not.toBe(api.upload.mock.calls[0][4]);
});
it('labels a delayed schedule preview with its initiating session after navigation',async()=>{
  let finish!:(value:unknown)=>void;api.preview.mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
  api.sessions.mockResolvedValue([{id:'session',title:'Synthetic session',sequence_no:1,revision:1},{id:'session-b',title:'Other session',sequence_no:2,revision:1}]);
  render(<Root/>);await ready();screen.getByText('Lịch sử phiên bản').closest('details')!.open=true;
  fireEvent.change(screen.getByLabelText('Hẹn giờ công bố'),{target:{value:'2030-11-01T15:00'}});fireEvent.click(screen.getByRole('button',{name:'Xem trước lịch'}));await waitFor(()=>expect(finish).toBeTypeOf('function'));
  fireEvent.click(screen.getByRole('button',{name:'2. Other session'}));await screen.findByRole('heading',{name:'Other session'});
  await act(async()=>finish({preview_id:'preview',confirmation_token:'token',expires_at:'2099-01-01T00:00:00Z'}));
  expect(await screen.findByRole('dialog',{name:'Xác nhận công bố học liệu'})).toHaveTextContent('Buổi Synthetic session.');expect(api.write).not.toHaveBeenCalled();
});
it('does not let an older schedule response replace a newer publication preview',async()=>{
  let finish!:(value:unknown)=>void;let calls=0;
  api.preview.mockImplementation(()=>++calls===1?new Promise(resolve=>{finish=resolve;}):Promise.resolve({preview_id:'new-preview',confirmation_token:'new-token',expires_at:'2099-01-01T00:00:00Z'}));
  render(<Root/>);await ready();screen.getByText('Lịch sử phiên bản').closest('details')!.open=true;
  const clock=screen.getByLabelText('Hẹn giờ công bố') as HTMLInputElement;
  fireEvent.change(clock,{target:{value:'2030-11-01T15:00'}});fireEvent.submit(clock.form!);await waitFor(()=>expect(finish).toBeTypeOf('function'));
  fireEvent.click(screen.getByRole('button',{name:'Công bố'}));await screen.findByText('Sinh viên của lớp sẽ được mở phiên bản này ngay sau khi công bố.');
  await act(async()=>finish({preview_id:'old-preview',confirmation_token:'old-token',expires_at:'2099-01-01T00:00:00Z'}));
  expect(screen.queryByText(/Tài liệu sẽ được công bố lúc/)).toBeNull();expect(screen.getByText('Sinh viên của lớp sẽ được mở phiên bản này ngay sau khi công bố.')).toBeVisible();expect(api.write).not.toHaveBeenCalled();
});
it('separates native file controls and retained files between two new-material sessions',async()=>{
  api.sessions.mockResolvedValue([{id:'session',title:'Synthetic session',sequence_no:1,revision:1},{id:'session-b',title:'Other session',sequence_no:2,revision:1}]);api.write.mockResolvedValue({id:material});
  render(<Root/>);await ready();screen.getByText('Thêm bài giảng PDF').closest('details')!.open=true;
  const firstInput=screen.getAllByLabelText('File PDF')[1] as HTMLInputElement,fileA=new File(['A'],'private-session-a.pdf');
  fireEvent.change(screen.getByLabelText('Tiêu đề bài giảng'),{target:{value:'Unsent session A material'}});fireEvent.change(firstInput,{target:{files:[fileA]}});
  fireEvent.click(screen.getByRole('button',{name:'2. Other session'}));await screen.findByRole('heading',{name:'Other session'});await ready();
  const secondInput=screen.getAllByLabelText('File PDF')[1] as HTMLInputElement;
  expect(secondInput).not.toBe(firstInput);expect(secondInput.files).toHaveLength(0);expect(screen.queryByText(/Tệp đang giữ trong tab: private-session-a.pdf/)).toBeNull();expect(screen.getByLabelText('Tiêu đề bài giảng')).toHaveValue('');
  const fileB=new File(['B'],'private-session-b.pdf');fireEvent.change(screen.getByLabelText('Tiêu đề bài giảng'),{target:{value:'Unsent session B material'}});fireEvent.change(secondInput,{target:{files:[fileB]}});
  fireEvent.click(screen.getByRole('button',{name:'1. Synthetic session'}));await screen.findByRole('heading',{name:'Synthetic session'});await ready();
  expect(screen.getByLabelText('Tiêu đề bài giảng')).toHaveValue('Unsent session A material');expect(screen.getByText(/Tệp đang giữ trong tab: private-session-a.pdf/)).toBeInTheDocument();expect(screen.queryByText(/Tệp đang giữ trong tab: private-session-b.pdf/)).toBeNull();
  fireEvent.submit((screen.getAllByLabelText('File PDF')[1] as HTMLInputElement).form!);await waitFor(()=>expect(api.upload).toHaveBeenCalled());expect(api.upload.mock.calls[0][1]).toBe(fileA);
});
