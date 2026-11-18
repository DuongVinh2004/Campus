import React from 'react';
import '@testing-library/jest-dom/vitest';
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {VersionChangeBanner} from './VersionChanges';
import {ChatDraftActor,ChatDraftSessionProvider} from '../chat/route-drafts';
const head={revision:3,mode:'WHOLE_DOCUMENT',target_version_id:'target',target_version_no:2,target_guidance:'Teacher-only current head',base_available:true,base_version_id:'base',base_version_no:1,reason:'Unreleased teacher reason',items:[]};
afterEach(()=>{cleanup();vi.restoreAllMocks();});
function Root({owner='teacher-role'}:{owner?:string}){return <ChatDraftSessionProvider><ChatDraftActor value={owner}><VersionChangeBanner actorId='same-account' versionId='target' onOpen={()=>{}}/></ChatDraftActor></ChatDraftSessionProvider>;}
it('hides an old role projection until the new role projection has been authorized',async()=>{
  vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify({change_set:head})));
  const view=render(<Root/>);await screen.findByText('Trang thay đổi trong phiên bản này');
  const details=screen.getByText('Trang thay đổi trong phiên bản này').closest('details')!;details.open=true;fireEvent(details,new Event('toggle'));
  expect(screen.getByText('Unreleased teacher reason')).toBeInTheDocument();
  let finish!:(value:Response)=>void;vi.mocked(fetch).mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
  view.rerender(<Root owner='student-role'/>);expect(screen.queryByText('Unreleased teacher reason')).toBeNull();
  await waitFor(()=>expect(finish).toBeTypeOf('function'));await act(async()=>finish(new Response(JSON.stringify({change_set:{...head,revision:2,reason:'Released student description',target_guidance:'Released guidance'}}))));
  expect(screen.queryByText('Unreleased teacher reason')).toBeNull();expect(screen.getByText('Released student description')).toBeInTheDocument();
});
