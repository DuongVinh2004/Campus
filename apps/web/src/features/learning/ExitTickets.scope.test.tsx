import React from 'react';
import '@testing-library/jest-dom/vitest';
import {act,cleanup,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {SessionExitTickets} from './ExitTickets';
import {ChatDraftActor,ChatDraftSessionProvider} from '../chat/route-drafts';
afterEach(()=>{cleanup();vi.restoreAllMocks();});
const rows=()=>{};
function Root({owner='teacher-role',manage=true}:{owner?:string;manage?:boolean}){return <ChatDraftSessionProvider><ChatDraftActor value={owner}><SessionExitTickets actorId='same-account' sessionId='session' materials={[]} instructions={[]} zoneId='Asia/Bangkok' canManage={manage} refresh={0} onRows={rows} onSelect={()=>{}}/></ChatDraftActor></ChatDraftSessionProvider>;}
it('hides teacher-only draft questions until the current role has an authorized list projection',async()=>{
  vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify({items:[{id:'ticket',state:'DRAFT',page_no:1,question:'Private unpublished teacher question'}]})));
  const view=render(<Root/>);await screen.findByRole('button',{name:'Private unpublished teacher question'});
  let finish!:(value:Response)=>void;vi.mocked(fetch).mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
  view.rerender(<Root owner='student-role' manage={false}/>);expect(screen.queryByText('Private unpublished teacher question')).toBeNull();
  await waitFor(()=>expect(finish).toBeTypeOf('function'));await act(async()=>finish(new Response(JSON.stringify({items:[]}))));
  expect(screen.queryByText('Private unpublished teacher question')).toBeNull();
});
