import React from "react";
import "@testing-library/jest-dom/vitest";
import { cleanup,fireEvent,render,screen,waitFor } from "@testing-library/react";
import { afterEach,beforeEach,expect,it,vi } from "vitest";
import { ExitTicketDetail } from "./ExitTicketDetail";
import { ChatDraftActor,ChatDraftSessionProvider,chatDraftActorScope } from "../chat/route-drafts";
import type {LearningMaterial} from "../../lib/data/api/learning-gateway";
const ticketId="00000000-0000-4000-8000-000000000004";
const version="00000000-0000-4000-8000-000000000006";
let denied=false;
let closed=false;
let reviewDenied=false;
let draftState=false;
let ticketRevision=3;
const materials:LearningMaterial[]=[{id:'material',offering_id:'offering',title:'Synthetic source',description:'',visibility:'VISIBLE',revision:1,current_published_version_id:version,
  versions:[{id:version,version_no:1,processing_state:'READY',publication_state:'PUBLISHED',page_count:3,has_text_layer:true,revision:1}]}];
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status});
beforeEach(()=>{
  denied=false;closed=false;reviewDenied=false;draftState=false;ticketRevision=3;
  vi.spyOn(globalThis,"fetch").mockImplementation(async(input)=>{
    const path=String(input);
    if(path.endsWith('/me/submission'))return json({submission:null});
    if(path.endsWith('/review'))return reviewDenied?json({code:'FORBIDDEN',detail:'Synthetic review denied'},403):json({review:null});
    if(denied)return json({code:'UNAUTHENTICATED',detail:'Synthetic session expired'},401);
    return json({id:ticketId,session_id:'session',revision:ticketRevision,state:draftState?'DRAFT':closed?'CLOSED':'OPEN',version_id:version,page_no:1,question:'Synthetic source-bound question',zone_id:'Asia/Bangkok',instruction:null,
      opens:{local:'2030-11-01T09:00',offset_minutes:420,utc:'2030-11-01T02:00:00Z'},closes:{local:'2030-11-01T10:00',offset_minutes:420,utc:'2030-11-01T03:00:00Z'}});
  });
});
afterEach(()=>{cleanup();vi.restoreAllMocks();});
function Root({open=true,staff=false,account,confirmWrite=async()=>{}}:{open?:boolean;staff?:boolean;account?:string;confirmWrite?:React.ComponentProps<typeof ExitTicketDetail>['confirmWrite']}){
  const actor=account??(staff?'teacher':'student');
  return <ChatDraftSessionProvider><ChatDraftActor value={chatDraftActorScope({user_id:actor,roles:[staff?'LECTURER':'STUDENT']})}>
    {open&&<ExitTicketDetail actorId={actor} ticketId={ticketId} staff={staff} canManage={staff} materials={materials} instructions={[]} zoneId="Asia/Bangkok" onClose={()=>{}} onOpen={()=>{}} onChange={()=>{}} confirmWrite={confirmWrite}/>}
  </ChatDraftActor></ChatDraftSessionProvider>;
}
it("retains an unsent private answer after leaving and reopening a ticket",async()=>{
  const instance=render(<Root/>);
  fireEvent.change(await screen.findByLabelText('Câu trả lời riêng'),{target:{value:'Unsent private answer'}});
  instance.rerender(<Root open={false}/>);instance.rerender(<Root/>);
  expect(await screen.findByLabelText('Câu trả lời riêng')).toHaveValue('Unsent private answer');
});
it("retains the teacher's unsaved private review after ticket unmount",async()=>{
  closed=true;const instance=render(<Root staff/>);
  fireEvent.click(await screen.findByRole('button',{name:'Soạn bản rà bài'}));
  fireEvent.change(screen.getByLabelText('Chủ đề lỗi thường gặp'),{target:{value:'Private unsaved review topics'}});
  instance.rerender(<Root staff open={false}/>);instance.rerender(<Root staff/>);
  expect(await screen.findByLabelText('Chủ đề lỗi thường gặp')).toHaveValue('Private unsaved review topics');
});
it("conceals an expired ticket response without destroying the original unsent answer",async()=>{
  render(<Root/>);fireEvent.change(await screen.findByLabelText('Câu trả lời riêng'),{target:{value:'Original answer before expiry'}});
  denied=true;fireEvent(window,new Event('focus'));await screen.findByRole('alert');
  expect(screen.queryByLabelText('Câu trả lời riêng')).toBeNull();
  denied=false;fireEvent(window,new Event('focus'));
  expect(await screen.findByLabelText('Câu trả lời riêng')).toHaveValue('Original answer before expiry');
});

it("preserves an uncertain send through unmount and requires a fresh receipt check before retry",async()=>{
  const keys:string[]=[];const bodies:unknown[]=[];
  vi.mocked(fetch).mockImplementation(async(input,init)=>{
    const path=String(input);
    if(init?.method==='PUT'){
      keys.push(new Headers(init.headers).get('Idempotency-Key')!);bodies.push(JSON.parse(String(init.body)));
      return keys.length===1?json({code:'UNAVAILABLE'},503):json({ticket_id:ticketId,answer:'Uncertain private answer',revision:1,receipt_id:'receipt-one',submitted_at:'2030-11-01T02:30:00Z'});
    }
    if(path.endsWith('/me/submission'))return json({submission:null});
    return json({id:ticketId,session_id:'session',revision:3,state:'OPEN',version_id:version,page_no:1,question:'Synthetic source-bound question',zone_id:'Asia/Bangkok',instruction:null,
      opens:{local:'2030-11-01T09:00',offset_minutes:420,utc:'2030-11-01T02:00:00Z'},closes:{local:'2030-11-01T10:00',offset_minutes:420,utc:'2030-11-01T03:00:00Z'}});
  });
  const instance=render(<Root/>);
  fireEvent.change(await screen.findByLabelText('Câu trả lời riêng'),{target:{value:'Uncertain private answer'}});
  fireEvent.click(screen.getByRole('button',{name:'Nộp câu trả lời'}));await screen.findByRole('button',{name:'Kiểm tra biên nhận'});
  instance.rerender(<Root open={false}/>);instance.rerender(<Root/>);
  expect(await screen.findByLabelText('Câu trả lời riêng')).toHaveValue('Uncertain private answer');
  expect(screen.queryByRole('button',{name:'Thử lại lần gửi'})).toBeNull();expect(keys).toHaveLength(1);
  fireEvent.click(screen.getByRole('button',{name:'Kiểm tra biên nhận'}));
  fireEvent.click(await screen.findByRole('button',{name:'Thử lại lần gửi'}));
  await screen.findByText('Đã nhận bài lần 1.');
  expect(keys).toHaveLength(2);expect(keys[1]).toBe(keys[0]);expect(bodies[1]).toEqual(bodies[0]);
});

it("hides a denied private review while retaining it for restored access",async()=>{
  closed=true;render(<Root staff/>);
  fireEvent.click(await screen.findByRole('button',{name:'Soạn bản rà bài'}));
  fireEvent.change(screen.getByLabelText('Chủ đề lỗi thường gặp'),{target:{value:'Original review before temporary denial'}});
  reviewDenied=true;fireEvent(window,new Event('focus'));
  await waitFor(()=>expect(screen.queryByLabelText('Chủ đề lỗi thường gặp')).toBeNull());
  reviewDenied=false;fireEvent(window,new Event('focus'));
  expect(await screen.findByLabelText('Chủ đề lỗi thường gặp')).toHaveValue('Original review before temporary denial');
});

it("publishes no old receipt or prose while another account's receipt is being verified",async()=>{
  const original=vi.mocked(fetch).getMockImplementation()!;
  let finish!:()=>void;
  vi.mocked(fetch).mockImplementation(async(input,init)=>{
    if(String(input).endsWith('/me/submission')){
      if(new Headers(init?.headers).get('X-Campus-Reader-Actor')==='student-b')return new Promise(resolve=>{finish=()=>resolve(json({submission:null}));});
      return json({submission:{ticket_id:ticketId,answer:'Saved private answer A',revision:1,receipt_id:'receipt-a',submitted_at:'2030-11-01T02:30:00Z'}});
    }
    return original(input,init);
  });
  const instance=render(<Root/>);
  fireEvent.change(await screen.findByLabelText('Câu trả lời riêng'),{target:{value:'Unsent private answer A'}});
  instance.rerender(<Root account="student-b"/>);
  expect(screen.queryByText('Saved private answer A')).toBeNull();
  expect(screen.queryByDisplayValue('Unsent private answer A')).toBeNull();
  await waitFor(()=>expect(finish).toBeTypeOf('function'));finish();
  expect(await screen.findByLabelText('Câu trả lời riêng')).toHaveValue('');
  instance.rerender(<Root/>);
  expect(await screen.findByLabelText('Câu trả lời riêng')).toHaveValue('Unsent private answer A');
});

it("retains the original edit revision and prose instead of adopting a newer server revision",async()=>{
  draftState=true;
  const original=vi.mocked(fetch).getMockImplementation()!;
  let submitted:Record<string,unknown>|undefined;
  vi.mocked(fetch).mockImplementation(async(input,init)=>{
    if(init?.method==='PATCH'){submitted=JSON.parse(String(init.body));return json({code:'REVISION_CONFLICT',detail:'Synthetic stale revision'},409);}
    return original(input,init);
  });
  const instance=render(<Root staff/>);
  fireEvent.click(await screen.findByRole('button',{name:'Sửa bản nháp'}));
  fireEvent.change(screen.getByLabelText('Câu hỏi vận dụng'),{target:{value:'Private edit based on revision three'}});
  instance.rerender(<Root staff open={false}/>);ticketRevision=4;instance.rerender(<Root staff/>);
  expect(await screen.findByLabelText('Câu hỏi vận dụng')).toHaveValue('Private edit based on revision three');
  fireEvent.click(screen.getByRole('button',{name:'Lưu bản nháp'}));await screen.findByRole('alert');
  expect(submitted?.revision).toBe(3);expect(screen.getByLabelText('Câu hỏi vận dụng')).toHaveValue('Private edit based on revision three');
});

it('keeps private review prose when returning to the summary and reopening the composer',async()=>{
  closed=true;render(<Root staff/>);fireEvent.click(await screen.findByRole('button',{name:'Soạn bản rà bài'}));
  fireEvent.change(screen.getByLabelText('Chủ đề lỗi thường gặp'),{target:{value:'Do not discard this private review'}});
  fireEvent.click(screen.getByRole('button',{name:'Quay lại'}));fireEvent.click(screen.getByRole('button',{name:'Soạn bản rà bài'}));
  expect(screen.getByLabelText('Chủ đề lỗi thường gặp')).toHaveValue('Do not discard this private review');
});

it('compares the private review, requires a conflict choice and leaves publication untouched',async()=>{
  closed=true;const original=vi.mocked(fetch).getMockImplementation()!;
  let review={revision:3,topics:'Saved topics',next_plan:'Saved plan',explanation:'Saved private explanation',published:null};
  const writes:Record<string,unknown>[]=[];
  vi.mocked(fetch).mockImplementation(async(input,init)=>{
    if(String(input).endsWith('/review')){
      if(init?.method==='PUT'){const payload=JSON.parse(String(init.body));writes.push(payload);review={...review,...payload,revision:5};return json(review);}
      return json({review});
    }
    return original(input,init);
  });
  render(<Root staff/>);fireEvent.click(await screen.findByRole('button',{name:'Soạn bản rà bài'}));
  fireEvent.change(screen.getByLabelText('Chủ đề lỗi thường gặp'),{target:{value:'My private topics'}});
  review={...review,revision:4,topics:'Other private topics',next_plan:'New server plan'};
  fireEvent.click(screen.getByRole('button',{name:'Đối chiếu bản trên máy chủ'}));await screen.findByLabelText('Chọn nội dung: Chủ đề lỗi thường gặp');
  expect(screen.getByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'})).toBeDisabled();expect(writes).toHaveLength(0);
  fireEvent.change(screen.getByLabelText('Chọn nội dung: Chủ đề lỗi thường gặp'),{target:{value:'mine'}});fireEvent.click(screen.getByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'}));
  expect(screen.getByLabelText('Kế hoạch buổi sau')).toHaveValue('New server plan');fireEvent.click(screen.getByRole('button',{name:'Lưu bản rà bài'}));
  await waitFor(()=>expect(writes).toHaveLength(1));expect(writes[0]).toMatchObject({operation:'SAVE_DRAFT',revision:4,topics:'My private topics',next_plan:'New server plan'});expect(review.published).toBeNull();
});

it('reopens a retained private review with its original revision and retries an uncertain save with the same key',async()=>{
  closed=true;const original=vi.mocked(fetch).getMockImplementation()!;
  let revision=3;const attempts:{payload:Record<string,unknown>;key:string|null}[]=[];
  vi.mocked(fetch).mockImplementation(async(input,init)=>{
    if(String(input).endsWith('/review')){
      if(init?.method==='PUT'){attempts.push({payload:JSON.parse(String(init.body)),key:new Headers(init.headers).get('Idempotency-Key')});return json({code:'UNAVAILABLE'},503);}
      return json({review:{revision,topics:'Server topics',next_plan:'Server plan',explanation:'Private server explanation',published:null}});
    }
    return original(input,init);
  });
  const view=render(<Root staff/>);fireEvent.click(await screen.findByRole('button',{name:'Soạn bản rà bài'}));fireEvent.change(screen.getByLabelText('Chủ đề lỗi thường gặp'),{target:{value:'Private old revision review'}});
  fireEvent.click(screen.getByRole('button',{name:'Quay lại'}));revision=4;fireEvent.click(screen.getByRole('button',{name:'Tải lại phiếu'}));await screen.findByText('Chủ đề lỗi · Server topics');
  fireEvent.click(screen.getByRole('button',{name:'Soạn bản rà bài'}));fireEvent.click(screen.getByRole('button',{name:'Lưu bản rà bài'}));await screen.findByRole('alert');
  expect(attempts[0].payload.revision).toBe(3);
  view.rerender(<Root staff open={false}/>);view.rerender(<Root staff/>);await screen.findByLabelText('Chủ đề lỗi thường gặp');fireEvent.click(screen.getByRole('button',{name:'Lưu bản rà bài'}));
  await waitFor(()=>expect(attempts).toHaveLength(2));expect(attempts[1]).toEqual(attempts[0]);expect(screen.getByLabelText('Chủ đề lỗi thường gặp')).toHaveValue('Private old revision review');
});

it('keeps a cancelled ticket edit attached to its original revision when the server changes before reopening',async()=>{
  draftState=true;const original=vi.mocked(fetch).getMockImplementation()!;const attempts:Record<string,unknown>[]=[];
  vi.mocked(fetch).mockImplementation(async(input,init)=>{if(init?.method==='PATCH'){attempts.push(JSON.parse(String(init.body)));return json({code:'REVISION_CONFLICT'},409);}return original(input,init);});
  render(<Root staff/>);fireEvent.click(await screen.findByRole('button',{name:'Sửa bản nháp'}));fireEvent.change(screen.getByLabelText('Câu hỏi vận dụng'),{target:{value:'Cancelled but retained original ticket prose'}});
  fireEvent.click(screen.getByRole('button',{name:'Quay lại'}));ticketRevision=4;fireEvent.click(screen.getByRole('button',{name:'Tải lại phiếu'}));
  await waitFor(()=>expect(screen.getByRole('button',{name:'Sửa bản nháp'})).toBeEnabled());fireEvent.click(screen.getByRole('button',{name:'Sửa bản nháp'}));
  expect(screen.getByLabelText('Câu hỏi vận dụng')).toHaveValue('Cancelled but retained original ticket prose');fireEvent.click(screen.getByRole('button',{name:'Lưu bản nháp'}));
  await waitFor(()=>expect(attempts).toHaveLength(1));expect(attempts[0].revision).toBe(3);
});

it('keeps the proposed extension and its original revision after returning and a newer ticket read',async()=>{
  const confirm=vi.fn<React.ComponentProps<typeof ExitTicketDetail>['confirmWrite']>().mockResolvedValue(undefined);
  render(<Root staff confirmWrite={confirm}/>);fireEvent.click(await screen.findByRole('button',{name:'Gia hạn nhận bài'}));
  fireEvent.change(screen.getByLabelText('Giờ đóng mới (Asia/Bangkok)'),{target:{value:'2030-11-01T12:00'}});
  fireEvent.click(screen.getByRole('button',{name:'Quay lại'}));ticketRevision=4;fireEvent.click(screen.getByRole('button',{name:'Tải lại phiếu'}));
  await waitFor(()=>expect(screen.getByRole('button',{name:'Gia hạn nhận bài'})).toBeEnabled());fireEvent.click(screen.getByRole('button',{name:'Gia hạn nhận bài'}));
  expect(screen.getByLabelText('Giờ đóng mới (Asia/Bangkok)')).toHaveValue('2030-11-01T12:00');
  fireEvent.click(screen.getByRole('button',{name:'Xem trước gia hạn'}));await waitFor(()=>expect(confirm).toHaveBeenCalled());
  expect(confirm.mock.calls[0][1]).toMatchObject({operation:'EXTEND',revision:3,closes:{local:'2030-11-01T12:00'}});
});

it('requires a clock conflict choice before adopting a newer extension revision',async()=>{
  const original=vi.mocked(fetch).getMockImplementation()!;
  const confirm=vi.fn<React.ComponentProps<typeof ExitTicketDetail>['confirmWrite']>().mockResolvedValue(undefined);
  render(<Root staff confirmWrite={confirm}/>);fireEvent.click(await screen.findByRole('button',{name:'Gia hạn nhận bài'}));
  fireEvent.change(screen.getByLabelText('Giờ đóng mới (Asia/Bangkok)'),{target:{value:'2030-11-01T12:00'}});
  vi.mocked(fetch).mockImplementation(async(input,init)=>{
    const response=await original(input,init);const value=await response.json();
    if(value.id===ticketId)return json({...value,revision:4,closes:{local:'2030-11-01T11:00',offset_minutes:420,utc:'2030-11-01T04:00:00Z'}});
    return json(value);
  });
  fireEvent.click(screen.getByRole('button',{name:'Đối chiếu bản trên máy chủ'}));await screen.findByLabelText('Chọn nội dung: Giờ đóng mới');
  expect(screen.getByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'})).toBeDisabled();expect(confirm).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Chọn nội dung: Giờ đóng mới'),{target:{value:'mine'}});fireEvent.click(screen.getByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'}));
  expect(screen.getByLabelText('Giờ đóng mới (Asia/Bangkok)')).toHaveValue('2030-11-01T12:00');
  fireEvent.click(screen.getByRole('button',{name:'Xem trước gia hạn'}));await waitFor(()=>expect(confirm).toHaveBeenCalled());
  expect(confirm.mock.calls[0][1]).toMatchObject({operation:'EXTEND',revision:4,closes:{local:'2030-11-01T12:00'}});
});

it('reports an extension preview failure once while keeping the proposed time',async()=>{
  const confirm=vi.fn<React.ComponentProps<typeof ExitTicketDetail>['confirmWrite']>().mockRejectedValue(new Error('Synthetic preview returned without confirmation'));
  render(<Root staff confirmWrite={confirm}/>);fireEvent.click(await screen.findByRole('button',{name:'Gia hạn nhận bài'}));
  fireEvent.change(screen.getByLabelText('Giờ đóng mới (Asia/Bangkok)'),{target:{value:'2030-11-01T12:00'}});fireEvent.click(screen.getByRole('button',{name:'Xem trước gia hạn'}));
  await screen.findByText('Synthetic preview returned without confirmation');expect(screen.getAllByText('Synthetic preview returned without confirmation')).toHaveLength(1);
  expect(screen.getByLabelText('Giờ đóng mới (Asia/Bangkok)')).toHaveValue('2030-11-01T12:00');
});
