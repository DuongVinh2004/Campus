import React from 'react';
import '@testing-library/jest-dom/vitest';
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {StudentPageFeedback,SessionPageFeedback} from './PageFeedback';
import {ChatDraftActor,ChatDraftSessionProvider,chatDraftActorScope} from '../chat/route-drafts';
const version='00000000-0000-4000-8000-000000000002';
const session='00000000-0000-4000-8000-000000000003';
const title='Em đang vướng ở trang này';
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status});
let denied=false;
beforeEach(()=>{
  denied=false;
  vi.spyOn(globalThis,'fetch').mockImplementation(async(input)=>{
    if(denied)return json({code:'FORBIDDEN',detail:'Synthetic denied read'},403);
    const path=String(input);
    if(path.includes('session-contexts'))return json({items:[{id:session,title:'Synthetic session'}]});
    if(path.includes('page-feedback-window'))return json({window:{closes_at:'2099-01-01T00:00:00Z'}});
    if(path.includes('page-feedback-summary'))return json({state:'NOT_OPENED',closes_at:null,pages:[]});
    return json({feedback:null});
  });
});
afterEach(()=>{cleanup();vi.restoreAllMocks();});
function Root({show=true,actor='student',page=2,teacher=false,configure=async()=>{}}:{show?:boolean;actor?:string;page?:number;teacher?:boolean;configure?:(closesAt:string)=>Promise<unknown>}){
  return <ChatDraftSessionProvider><ChatDraftActor value={chatDraftActorScope({user_id:actor,roles:[teacher?'LECTURER':'STUDENT']})}>
    {show&&(teacher?<SessionPageFeedback actorId={actor} sessionId={session} startsAt={null} timeZone='Asia/Bangkok' canOpen onConfigure={configure} onOpen={()=>{}}/>:
      <StudentPageFeedback actorId={actor} versionId={version} versionNumber={1} pageNo={page} sourceSessionId={session} timeZone='Asia/Bangkok'/>)}
  </ChatDraftActor></ChatDraftSessionProvider>;
}
async function open(){fireEvent.click(screen.getByRole('button',{name:title}));await screen.findByRole('radio',{name:'Cần thêm ví dụ'});}
it('keeps independent unsent page choices after closing and reopening the dialog',async()=>{
  const view=render(<Root/>);await open();fireEvent.click(screen.getByRole('radio',{name:'Cần thêm ví dụ'}));
  fireEvent.click(screen.getByRole('button',{name:'Đóng'}));
  view.rerender(<Root page={4}/>);await open();fireEvent.click(screen.getByRole('radio',{name:'Nghi lỗi tài liệu'}));
  fireEvent.click(screen.getByRole('button',{name:'Đóng'}));view.rerender(<Root/>);await open();
  expect(screen.getByRole('radio',{name:'Cần thêm ví dụ'})).toBeChecked();
  fireEvent.click(screen.getByRole('button',{name:'Đóng'}));view.rerender(<Root page={4}/>);await open();
  expect(screen.getByRole('radio',{name:'Nghi lỗi tài liệu'})).toBeChecked();
});
it('restores the owner choice after actual route unmount',async()=>{
  const view=render(<Root/>);await open();fireEvent.click(screen.getByRole('radio',{name:'Cần thêm ví dụ'}));
  view.rerender(<Root show={false}/>);view.rerender(<Root/>);
  if(!screen.queryByRole('dialog'))await open();
  expect(await screen.findByRole('radio',{name:'Cần thêm ví dụ'})).toBeChecked();
});
it('retains an uncertain service-error request through close/reopen and retries exactly',async()=>{
  const original=vi.mocked(fetch).getMockImplementation()!;
  const writes:{key:string|null;body:unknown}[]=[];
  vi.mocked(fetch).mockImplementation(async(input,init)=>{
    if(init?.method==='PUT'){
      writes.push({key:new Headers(init.headers).get('Idempotency-Key'),body:JSON.parse(String(init.body))});
      return writes.length===1?json({code:'UNAVAILABLE',detail:'Synthetic uncertain save'},503):json({id:'receipt',session_id:session,category:'NEED_EXAMPLE',status:'ACTIVE',revision:1});
    }
    return original(input,init);
  });
  render(<Root/>);await open();fireEvent.click(screen.getByRole('radio',{name:'Cần thêm ví dụ'}));
  await waitFor(()=>expect(screen.getByRole('button',{name:'Gửi báo vướng'})).toBeEnabled());
  fireEvent.click(screen.getByRole('button',{name:'Gửi báo vướng'}));
  await waitFor(()=>expect(screen.getByRole('alert')).toHaveTextContent('Dịch vụ học liệu chưa sẵn sàng'));
  fireEvent.click(screen.getByRole('button',{name:'Đóng'}));await open();
  fireEvent.click(await screen.findByRole('button',{name:'Kiểm tra và thử lại'}));await screen.findByText('Đã lưu phản hồi.');
  expect(writes).toHaveLength(2);expect(writes[1]).toEqual(writes[0]);
});
it('keeps an unsaved class cutoff through route unmount',async()=>{
  const view=render(<Root teacher actor='teacher'/>);
  fireEvent.change(await screen.findByLabelText('Giờ chốt (Asia/Bangkok)'),{target:{value:'2030-11-01T15:00'}});
  view.rerender(<Root teacher actor='teacher' show={false}/>);view.rerender(<Root teacher actor='teacher'/>);
  expect(await screen.findByLabelText('Giờ chốt (Asia/Bangkok)')).toHaveValue('2030-11-01T15:00');
});
it('separates the choices of two accounts and restores the original owner',async()=>{
  const view=render(<Root/>);await open();fireEvent.click(screen.getByRole('radio',{name:'Cần thêm ví dụ'}));
  view.rerender(<Root actor='student-b'/>);expect(screen.queryByRole('dialog')).toBeNull();await open();
  expect(screen.getByRole('radio',{name:'Khó hiểu'})).toBeChecked();
  view.rerender(<Root/>);expect(await screen.findByRole('radio',{name:'Cần thêm ví dụ'})).toBeChecked();
});
it('hides denied context reads and recovers the same private choice',async()=>{
  const view=render(<Root/>);await open();fireEvent.click(screen.getByRole('radio',{name:'Nghi lỗi tài liệu'}));
  view.rerender(<Root show={false}/>);denied=true;view.rerender(<Root/>);
  await waitFor(()=>expect(screen.getByRole('alert')).not.toBeEmptyDOMElement());
  expect(screen.queryByRole('radio')).toBeNull();
  view.rerender(<Root show={false}/>);denied=false;view.rerender(<Root/>);
  expect(await screen.findByRole('radio',{name:'Nghi lỗi tài liệu'})).toBeChecked();
});
it('checks a committed receipt after route unmount without replaying its lost response',async()=>{
  const original=vi.mocked(fetch).getMockImplementation()!;let writes=0;
  const own={id:'receipt',session_id:session,category:'NEED_EXAMPLE',status:'ACTIVE',revision:1};
  vi.mocked(fetch).mockImplementation(async(input,init)=>{
    if(init?.method==='PUT'){writes++;return json({code:'UNAVAILABLE'},503);}
    if(String(input).endsWith('/me/feedback'))return json({feedback:writes?own:null});
    return original(input,init);
  });
  const view=render(<Root/>);await open();fireEvent.click(screen.getByRole('radio',{name:'Cần thêm ví dụ'}));
  await waitFor(()=>expect(screen.getByRole('button',{name:'Gửi báo vướng'})).toBeEnabled());
  fireEvent.click(screen.getByRole('button',{name:'Gửi báo vướng'}));await screen.findByRole('button',{name:'Kiểm tra và thử lại'});
  view.rerender(<Root show={false}/>);view.rerender(<Root/>);
  fireEvent.click(await screen.findByRole('button',{name:'Kiểm tra và thử lại'}));await screen.findByText('Đã kiểm tra và hiển thị trạng thái hiện tại.');
  expect(writes).toBe(1);expect(screen.queryByRole('button',{name:'Kiểm tra và thử lại'})).toBeNull();
});
it('waits for the original cutoff preview operation after remount',async()=>{
  let finish!:(value:unknown)=>void;
  const configure=vi.fn((_closesAt:string)=>new Promise(resolve=>{finish=resolve;}));
  const view=render(<Root teacher actor='teacher' configure={configure}/>);
  fireEvent.change(await screen.findByLabelText('Giờ chốt (Asia/Bangkok)'),{target:{value:'2030-11-01T15:00'}});
  fireEvent.click(screen.getByRole('button',{name:'Xem trước và mở báo vướng'}));await waitFor(()=>expect(configure).toHaveBeenCalledTimes(1));
  view.rerender(<Root teacher actor='teacher' configure={configure} show={false}/>);view.rerender(<Root teacher actor='teacher' configure={configure}/>);
  expect(await screen.findByLabelText('Giờ chốt (Asia/Bangkok)')).toBeDisabled();
  await act(async()=>finish({}));
  await waitFor(()=>expect(screen.getByLabelText('Giờ chốt (Asia/Bangkok)')).toBeEnabled());
  expect(screen.getByLabelText('Giờ chốt (Asia/Bangkok)')).toHaveValue('2030-11-01T15:00');
  expect(configure).toHaveBeenCalledTimes(1);expect(configure).toHaveBeenCalledWith('2030-11-01T08:00:00.000Z');
});
