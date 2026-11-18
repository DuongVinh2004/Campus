import React from 'react';
import '@testing-library/jest-dom/vitest';
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {LearningWorkspace} from './LearningWorkspace';
import {ChatDraftActor,ChatDraftSessionProvider,chatDraftActorScope} from '../chat/route-drafts';
const api=vi.hoisted(()=>({capabilities:vi.fn(),offerings:vi.fn(),sessions:vi.fn(),materials:vi.fn(),list:vi.fn(),request:vi.fn(),write:vi.fn()}));
vi.mock('../../lib/data/api/learning-gateway',()=>({LearningGateway:class{capabilities=api.capabilities;offerings=api.offerings;sessions=api.sessions;materials=api.materials;list=api.list;request=api.request;write=api.write;},LearningApiError:class extends Error{}}));
vi.mock('../../components/AppShell',()=>({AppShell:({children}:{children:React.ReactNode})=><ChatDraftActor value={chatDraftActorScope({user_id:currentActor,roles:currentRoles})}>{children}</ChatDraftActor>}));
vi.mock('./LearningNotifications',()=>({LearningNotifications:()=>null}));vi.mock('./ReadingInstructions',()=>({ReadingInstructions:()=>null}));vi.mock('./reader/LearningPdfReader',()=>({LearningPdfReader:()=>null}));
const classA='00000000-0000-4000-8000-000000000001',classB='00000000-0000-4000-8000-000000000002';
let currentActor='admin',currentRoles=['SYSTEM_ADMIN'];
beforeEach(()=>{
  currentActor='admin';currentRoles=['SYSTEM_ADMIN'];vi.stubGlobal('BroadcastChannel',undefined);
  vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({user_id:currentActor,roles:currentRoles}))));
  api.capabilities.mockResolvedValue({available:true});api.offerings.mockResolvedValue([classA,classB].map((id,index)=>({id,title:index?'Class B':'Class A',status:'ACTIVE',revision:1,capabilities:{read:false,manage:false}})));
  api.sessions.mockResolvedValue([]);api.materials.mockResolvedValue([]);api.request.mockResolvedValue({});
  api.list.mockImplementation(async(path:string)=>path==='/terms'?[{id:'term',name:'Synthetic term'}]:path==='/courses'?[{id:'course',name:'Synthetic course'}]:path==='/admin/eligible-actors'?[{id:'actor-a',display_name:'Actor A'},{id:'actor-b',display_name:'Actor B'}]:path.includes(classA)?[{id:'member-a',display_name:'Member A',role:'STUDENT',revision:1}]:path.includes(classB)?[{id:'member-b',display_name:'Member B',role:'STUDENT',revision:1}]:[]);
});
afterEach(()=>{cleanup();vi.resetAllMocks();vi.unstubAllGlobals();});
function Root({show=true}:{show?:boolean}){return <ChatDraftSessionProvider>{show&&<LearningWorkspace/>}</ChatDraftSessionProvider>;}
async function ready(){
  await screen.findByText('Quản trị học kỳ, môn học và thành viên');const details=screen.getByText('Quản trị học kỳ, môn học và thành viên').closest('details')!;
  if(!details.open){details.open=true;fireEvent(details,new Event('toggle'));}
  await screen.findByRole('option',{name:'Synthetic term'});await waitFor(()=>expect(screen.getByRole('button',{name:'Tạo học kỳ'})).toBeEnabled());
}
function draft(){
  for(const [name,value] of [['Tên học kỳ','Unsent term'],['Ngày bắt đầu','2030-01-01'],['Ngày kết thúc','2030-06-01'],['Mã môn','UNSENT-C'],['Tên môn','Unsent course'],['Mã lớp','UNSENT-SECTION'],['Tên lớp','Unsent class']])fireEvent.change(screen.getByLabelText(name),{target:{value}});
  fireEvent.change(screen.getByLabelText('Học kỳ'),{target:{value:'term'}});fireEvent.change(screen.getByLabelText('Môn học'),{target:{value:'course'}});
}
it('keeps all three unsent administrative creation forms through actual route unmount',async()=>{
  const view=render(<Root/>);await ready();draft();view.rerender(<Root show={false}/>);view.rerender(<Root/>);await ready();
  expect(screen.getByLabelText('Tên học kỳ')).toHaveValue('Unsent term');expect(screen.getByLabelText('Ngày bắt đầu')).toHaveValue('2030-01-01');expect(screen.getByLabelText('Ngày kết thúc')).toHaveValue('2030-06-01');
  expect(screen.getByLabelText('Mã môn')).toHaveValue('UNSENT-C');expect(screen.getByLabelText('Tên môn')).toHaveValue('Unsent course');expect(screen.getByLabelText('Mã lớp')).toHaveValue('UNSENT-SECTION');expect(screen.getByLabelText('Tên lớp')).toHaveValue('Unsent class');expect(screen.getByLabelText('Học kỳ')).toHaveValue('term');expect(screen.getByLabelText('Môn học')).toHaveValue('course');expect(api.write).not.toHaveBeenCalled();
});
it('keeps separate proposed member and role selections for each offering',async()=>{
  render(<Root/>);await ready();fireEvent.change(screen.getByLabelText('Tài khoản'),{target:{value:'actor-a'}});fireEvent.change(screen.getByLabelText('Vai trò trong lớp'),{target:{value:'INSTRUCTOR'}});
  fireEvent.change(screen.getByLabelText('Lớp học phần'),{target:{value:classB}});await waitFor(()=>expect(screen.getByLabelText('Lớp học phần')).toHaveValue(classB));
  expect(screen.getByLabelText('Tài khoản')).toHaveValue('');expect(screen.getByLabelText('Vai trò trong lớp')).toHaveValue('STUDENT');
  fireEvent.change(screen.getByLabelText('Tài khoản'),{target:{value:'actor-b'}});fireEvent.change(screen.getByLabelText('Lớp học phần'),{target:{value:classA}});await waitFor(()=>expect(screen.getByLabelText('Lớp học phần')).toHaveValue(classA));
  expect(screen.getByLabelText('Tài khoản')).toHaveValue('actor-a');expect(screen.getByLabelText('Vai trò trong lớp')).toHaveValue('INSTRUCTOR');expect(api.write).not.toHaveBeenCalled();
});
it('does not display the previous offering member controls after switching offerings',async()=>{
  render(<Root/>);await ready();await screen.findByText(/Member A/);
  fireEvent.change(screen.getByLabelText('Lớp học phần'),{target:{value:classB}});await waitFor(()=>expect(screen.getByLabelText('Lớp học phần')).toHaveValue(classB));
  expect(screen.queryByText(/Member A/)).toBeNull();await screen.findByText(/Member B/);expect(api.write).not.toHaveBeenCalled();
});
it('separates administrator identities and hides administration when the role is absent',async()=>{
  const view=render(<Root/>);await ready();draft();view.rerender(<Root show={false}/>);currentActor='admin-b';view.rerender(<Root/>);await ready();
  expect(screen.getByLabelText('Tên học kỳ')).toHaveValue('');expect(screen.getByLabelText('Mã môn')).toHaveValue('');
  view.rerender(<Root show={false}/>);currentActor='teacher';currentRoles=['LECTURER'];view.rerender(<Root/>);await screen.findByRole('heading',{name:'Học liệu theo buổi học'});
  expect(screen.queryByText('Quản trị học kỳ, môn học và thành viên')).toBeNull();
  view.rerender(<Root show={false}/>);currentActor='admin';currentRoles=['SYSTEM_ADMIN'];view.rerender(<Root/>);await ready();expect(screen.getByLabelText('Tên học kỳ')).toHaveValue('Unsent term');expect(screen.getByLabelText('Mã môn')).toHaveValue('UNSENT-C');expect(api.write).not.toHaveBeenCalled();
});
it('retains an unconfirmed course proposal after true unmount without leaving its form locked',async()=>{
  api.write.mockResolvedValue({preview_id:'preview',confirmation_token:'token',expires_at:'2099-01-01T00:00:00Z',payload:{}});
  const view=render(<Root/>);await ready();fireEvent.change(screen.getByLabelText('Mã môn'),{target:{value:'UNSENT-C'}});fireEvent.change(screen.getByLabelText('Tên môn'),{target:{value:'Unsent course'}});
  fireEvent.click(screen.getByRole('button',{name:'Tạo môn học'}));const proposal=await screen.findByRole('dialog',{name:'Tạo môn học'});expect(proposal).not.toHaveTextContent('Lớp của thao tác:');expect(proposal).toHaveTextContent('Bản ghi mới chưa được tạo.');expect(screen.getByRole('button',{name:'Xác nhận thay đổi'})).toBeDisabled();
  view.rerender(<Root show={false}/>);view.rerender(<Root/>);await ready();await waitFor(()=>expect(screen.getByLabelText('Mã môn')).toBeEnabled());expect(screen.getByLabelText('Mã môn')).toHaveValue('UNSENT-C');expect(api.write.mock.calls.every(call=>call[0]==='/action-previews')).toBe(true);
});
it('ignores a delayed old catalog even when the transport ignores its abort signal',async()=>{
  const original=api.list.getMockImplementation()!;let hold=false,finish!:(value:unknown)=>void;let signal:AbortSignal|undefined;
  api.list.mockImplementation(async(path:string,requestSignal?:AbortSignal)=>hold&&path.includes(classA)&&path.endsWith('/members')?(signal=requestSignal,new Promise(resolve=>{finish=resolve;})):original(path,requestSignal));
  render(<Root/>);await ready();await screen.findByText(/Member A/);hold=true;
  const details=screen.getByText('Quản trị học kỳ, môn học và thành viên').closest('details')!;details.open=false;fireEvent(details,new Event('toggle'));details.open=true;fireEvent(details,new Event('toggle'));await waitFor(()=>expect(finish).toBeTypeOf('function'));
  fireEvent.change(screen.getByLabelText('Lớp học phần'),{target:{value:classB}});await screen.findByText(/Member B/);expect(signal?.aborted).toBe(true);
  await act(async()=>finish([{id:'late-a',display_name:'Late Member A',role:'INSTRUCTOR',revision:1}]));expect(screen.queryByText(/Late Member A/)).toBeNull();expect(screen.getByText(/Member B/)).toBeInTheDocument();
});
it('does not navigate a different selected offering when an original create preview is confirmed',async()=>{
  let finish!:(value:unknown)=>void;
  api.write.mockImplementation(async(path:string)=>path==='/action-previews'?new Promise(resolve=>{finish=resolve;}):{id:'created-offering'});
  render(<Root/>);await ready();draft();fireEvent.click(screen.getByRole('button',{name:'Tạo lớp'}));await waitFor(()=>expect(finish).toBeTypeOf('function'));
  fireEvent.change(screen.getByLabelText('Lớp học phần'),{target:{value:classB}});await waitFor(()=>expect(screen.getByLabelText('Lớp học phần')).toHaveValue(classB));
  await act(async()=>finish({preview_id:'preview',confirmation_token:'token',expires_at:'2099-01-01T00:00:00Z',payload:{}}));
  const proposal=await screen.findByRole('dialog',{name:'Tạo lớp học phần'});expect(proposal).not.toHaveTextContent('Lớp của thao tác:');expect(proposal).toHaveTextContent('Unsent class');
  fireEvent.click(screen.getByLabelText('Tôi đã kiểm tra thông tin và tác động.'));fireEvent.click(screen.getByRole('button',{name:'Xác nhận thay đổi'}));
  await waitFor(()=>expect(screen.getByLabelText('Tên lớp')).toHaveValue(''));expect(screen.getByLabelText('Lớp học phần')).toHaveValue(classB);expect(api.write.mock.calls.filter(call=>call[0]==='/offerings')).toHaveLength(1);
});
it('hides member controls after failed revalidation while preserving the proposed member draft',async()=>{
  const original=api.list.getMockImplementation()!;let denied=false;
  api.list.mockImplementation(async(path:string,signal?:AbortSignal)=>{if(denied&&path.endsWith('/members'))throw new Error('Synthetic member read denied');return original(path,signal);});
  render(<Root/>);await ready();await screen.findByText(/Member A/);fireEvent.change(screen.getByLabelText('Tài khoản'),{target:{value:'actor-a'}});fireEvent.change(screen.getByLabelText('Vai trò trong lớp'),{target:{value:'INSTRUCTOR'}});
  const details=screen.getByText('Quản trị học kỳ, môn học và thành viên').closest('details')!;
  denied=true;details.open=false;fireEvent(details,new Event('toggle'));details.open=true;fireEvent(details,new Event('toggle'));await screen.findByText('Synthetic member read denied');
  expect(screen.queryByText(/Member A/)).toBeNull();expect(screen.getByLabelText('Tài khoản')).toHaveValue('actor-a');expect(screen.getByLabelText('Vai trò trong lớp')).toHaveValue('INSTRUCTOR');
  denied=false;details.open=false;fireEvent(details,new Event('toggle'));details.open=true;fireEvent(details,new Event('toggle'));await screen.findByText(/Member A/);expect(screen.getByLabelText('Tài khoản')).toHaveValue('actor-a');expect(api.write).not.toHaveBeenCalled();
});
it('keeps consecutive changes to multiple fields within the same event batch',async()=>{
  render(<Root/>);await ready();
  act(()=>{
    fireEvent.change(screen.getByLabelText('Tên học kỳ'),{target:{value:'Rapid term draft'}});
    fireEvent.change(screen.getByLabelText('Ngày bắt đầu'),{target:{value:'2030-01-01'}});
    fireEvent.change(screen.getByLabelText('Ngày kết thúc'),{target:{value:'2030-06-01'}});
  });
  expect(screen.getByLabelText('Tên học kỳ')).toHaveValue('Rapid term draft');expect(screen.getByLabelText('Ngày bắt đầu')).toHaveValue('2030-01-01');expect(screen.getByLabelText('Ngày kết thúc')).toHaveValue('2030-06-01');
});
