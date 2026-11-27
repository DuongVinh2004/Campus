import React from 'react';
import '@testing-library/jest-dom/vitest';
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {afterEach,expect,it,vi,type Mock} from 'vitest';
import {LearningMetadataForm} from './LearningMetadataForm';
import type {MetadataSnapshot} from './LearningMetadataComparison';
import {ChatDraftActor,ChatDraftSessionProvider} from '../chat/route-drafts';

afterEach(cleanup);
const initial={values:{title:'Original title',description:'Original description'},basis:{revision:3}};
const latest={values:{title:'Server title',description:'Server description'},basis:{revision:4}};
type Save=(payload:Record<string,unknown>,key:string)=>Promise<unknown>;
type Props={actor?:string;record?:string;show?:boolean;read:(signal:AbortSignal)=>Promise<MetadataSnapshot>;save?:Mock<Save>};
function Root({actor='teacher',record='record-a',show=true,read,save=vi.fn<Save>()}:Props){
  return <ChatDraftSessionProvider><ChatDraftActor value={actor}>{show&&<LearningMetadataForm actorId={actor} draftId={record} initialValues={initial.values} basis={initial.basis}
    fieldLabels={{title:'Title',description:'Description'}} onRead={read} onSave={save} toPayload={({values,basis})=>({...values,revision:basis.revision})}>
    {(values,change)=><><label>Title<input value={values.title} onChange={event=>change('title',event.target.value)}/></label><label>Description<textarea value={values.description} onChange={event=>change('description',event.target.value)}/></label><button>Preview</button></>}
  </LearningMetadataForm>}</ChatDraftActor></ChatDraftSessionProvider>;
}
const compare=()=>fireEvent.click(screen.getByRole('button',{name:'Đối chiếu bản trên máy chủ'}));
const apply=()=>fireEvent.click(screen.getByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'}));

it('retains unresolved comparison choices through route navigation without updating the write revision',async()=>{
  const read=vi.fn().mockResolvedValue(latest),save=vi.fn<Save>().mockRejectedValue(new Error('Synthetic preview failure'));
  const view=render(<Root read={read} save={save}/>);fireEvent.change(screen.getByLabelText('Title'),{target:{value:'My title'}});compare();
  await screen.findByLabelText('Chọn nội dung: Title');expect(screen.getByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'})).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Chọn nội dung: Title'),{target:{value:'server'}});
  view.rerender(<Root read={read} save={save} show={false}/>);view.rerender(<Root read={read} save={save}/>);
  expect(screen.getByLabelText('Chọn nội dung: Title')).toHaveValue('server');expect(screen.getByLabelText('Title')).toHaveValue('My title');
  fireEvent.click(screen.getByRole('button',{name:'Preview'}));await waitFor(()=>expect(save).toHaveBeenCalled());expect(save.mock.calls[0][0].revision).toBe(3);
  await screen.findByText('Synthetic preview failure');apply();
  expect(screen.getByLabelText('Title')).toHaveValue('Server title');expect(screen.getByLabelText('Description')).toHaveValue('Server description');
  expect(within(screen.getByRole('region',{name:'Nháp đã giữ 1'})).getByText('My title')).toBeInTheDocument();
  expect(save).toHaveBeenCalledTimes(1);
});

it('ignores an in-flight comparison when the draft changes before the read completes',async()=>{
  let finish!:(value:MetadataSnapshot)=>void;
  const read=vi.fn(()=>new Promise<MetadataSnapshot>(resolve=>{finish=resolve;}));
  render(<Root read={read}/>);fireEvent.change(screen.getByLabelText('Title'),{target:{value:'First edit'}});compare();await waitFor(()=>expect(finish).toBeTypeOf('function'));
  fireEvent.change(screen.getByLabelText('Title'),{target:{value:'More recent edit'}});await act(async()=>finish(latest));
  expect(screen.getByLabelText('Title')).toHaveValue('More recent edit');expect(screen.queryByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'})).toBeNull();
});

it.each(['owner','record','route'] as const)('aborts comparison across %s changes even when the transport ignores cancellation',async kind=>{
  let finish!:(value:MetadataSnapshot)=>void;let signal!:AbortSignal;
  const read=vi.fn((value:AbortSignal)=>{signal=value;return new Promise<MetadataSnapshot>(resolve=>{finish=resolve;});});
  const view=render(<Root read={read}/>);fireEvent.change(screen.getByLabelText('Title'),{target:{value:'Private old draft'}});compare();await waitFor(()=>expect(finish).toBeTypeOf('function'));
  const changed=kind==='owner'?{actor:'other-teacher'}:kind==='record'?{record:'record-b'}:{show:false};
  view.rerender(<Root read={read} {...changed}/>);expect(signal.aborted).toBe(true);await act(async()=>finish(latest));
  view.rerender(<Root read={read}/>);expect(screen.getByLabelText('Title')).toHaveValue('Private old draft');
  expect(screen.queryByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'})).toBeNull();expect(screen.getByRole('button',{name:'Đối chiếu bản trên máy chủ'})).toBeEnabled();
});

it('hides an older comparison when a fresh read is denied and preserves the original draft and revision',async()=>{
  const read=vi.fn().mockResolvedValueOnce(latest).mockRejectedValueOnce(new Error('Synthetic access denied'));
  const save=vi.fn<Save>().mockRejectedValue(new Error('Keep synthetic draft'));
  render(<Root read={read} save={save}/>);fireEvent.change(screen.getByLabelText('Title'),{target:{value:'Private edit'}});compare();await screen.findByLabelText('Chọn nội dung: Title');
  // The button reads "Đang đọc…" until the loading state clears one update later; wait for it instead of querying synchronously.
  await screen.findByRole('button',{name:'Đối chiếu bản trên máy chủ'});compare();
  await screen.findByText('Synthetic access denied');expect(screen.queryByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'})).toBeNull();expect(screen.queryByText('Server description')).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'Preview'}));await waitFor(()=>expect(save).toHaveBeenCalled());expect(save.mock.calls[0][0]).toMatchObject({title:'Private edit',revision:3});
});

it('starts a new three-way baseline after adoption and retains every previous draft',async()=>{
  const read=vi.fn().mockResolvedValueOnce({...latest,values:{title:'Original title',description:'Server description'}})
    .mockResolvedValueOnce({values:{title:'My title',description:'Third server description'},basis:{revision:5}});
  const save=vi.fn<Save>().mockRejectedValue(new Error('Synthetic keep draft'));
  render(<Root read={read} save={save}/>);fireEvent.change(screen.getByLabelText('Title'),{target:{value:'My title'}});compare();await screen.findByText('Server description');apply();
  fireEvent.change(screen.getByLabelText('Description'),{target:{value:'My second description'}});compare();await screen.findByLabelText('Chọn nội dung: Description');
  fireEvent.change(screen.getByLabelText('Chọn nội dung: Description'),{target:{value:'server'}});apply();
  expect(screen.getByLabelText('Title')).toHaveValue('My title');expect(screen.getByLabelText('Description')).toHaveValue('Third server description');
  expect(screen.getByText('Nháp trước khi đối chiếu (2)')).toBeInTheDocument();
  expect(within(screen.getByRole('region',{name:'Nháp đã giữ 2'})).getByText('My second description')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Preview'}));await waitFor(()=>expect(save).toHaveBeenCalled());expect(save.mock.calls[0][0].revision).toBe(5);
});

it.each([undefined,0,2,4.5])('rejects an incomplete or regressed server revision %s without rebasing',async revision=>{
  const read=vi.fn().mockResolvedValue({...latest,basis:{revision}});
  render(<Root read={read}/>);fireEvent.change(screen.getByLabelText('Title'),{target:{value:'My retained title'}});compare();
  await screen.findByText('Bản trên máy chủ chưa đủ thông tin để đối chiếu.');
  expect(screen.getByLabelText('Title')).toHaveValue('My retained title');expect(screen.queryByRole('button',{name:'Dùng kết quả đối chiếu để soạn tiếp'})).toBeNull();
});

it('sends the latest retained fields when editing and submitting in the same event batch',async()=>{
  const save=vi.fn<Save>().mockRejectedValue(new Error('Synthetic retained result'));
  render(<Root read={async()=>latest} save={save}/>);
  act(()=>{
    fireEvent.change(screen.getByLabelText('Title'),{target:{value:'Latest title in batch'}});
    fireEvent.change(screen.getByLabelText('Description'),{target:{value:'Latest description in batch'}});
    fireEvent.submit(screen.getByRole('button',{name:'Preview'}).closest('form')!);
  });
  await screen.findByText('Synthetic retained result');
  expect(save).toHaveBeenCalledTimes(1);
  expect(save.mock.calls[0][0]).toEqual({title:'Latest title in batch',description:'Latest description in batch',revision:3});
});

it('starts only one request for two submissions in the same event batch',async()=>{
  let finish!:(value:unknown)=>void;
  const save=vi.fn<Save>(()=>new Promise(resolve=>{finish=resolve;}));
  render(<Root read={async()=>latest} save={save}/>);
  const form=screen.getByRole('button',{name:'Preview'}).closest('form')!;
  act(()=>{fireEvent.submit(form);fireEvent.submit(form);});
  await waitFor(()=>expect(save).toHaveBeenCalled());
  const count=save.mock.calls.length;
  await act(async()=>finish({accepted:true}));
  expect(count).toBe(1);
});

it('keeps one pending request through remount and preserves a newer draft on acknowledgement',async()=>{
  let finish!:(value:unknown)=>void;
  const save=vi.fn<Save>(()=>new Promise(resolve=>{finish=resolve;})),read=async()=>latest;
  const view=render(<Root read={read} save={save}/>);
  fireEvent.change(screen.getByLabelText('Title'),{target:{value:'Submitted title'}});
  fireEvent.submit(screen.getByRole('button',{name:'Preview'}).closest('form')!);
  await waitFor(()=>expect(save).toHaveBeenCalledTimes(1));
  view.rerender(<Root read={read} save={save} show={false}/>);view.rerender(<Root read={read} save={save}/>);
  expect(screen.getByRole('button',{name:'Preview'})).toBeDisabled();
  fireEvent.submit(screen.getByRole('button',{name:'Preview'}).closest('form')!);
  fireEvent.change(screen.getByLabelText('Title'),{target:{value:'Newer retained title'}});
  await act(async()=>finish({accepted:true}));
  expect(save).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText('Title')).toHaveValue('Newer retained title');
});

it('blocks duplicate requests even when used without a retained-draft provider',async()=>{
  let finish!:(value:unknown)=>void;
  const save=vi.fn<Save>(()=>new Promise(resolve=>{finish=resolve;}));
  render(<LearningMetadataForm actorId='teacher' draftId='standalone' initialValues={{title:'Standalone'}} toPayload={({values})=>values} onSave={save}>{()=> <button>Standalone save</button>}</LearningMetadataForm>);
  const form=screen.getByRole('button',{name:'Standalone save'}).closest('form')!;
  act(()=>{fireEvent.submit(form);fireEvent.submit(form);});
  await waitFor(()=>expect(save).toHaveBeenCalled());const count=save.mock.calls.length;
  await act(async()=>finish({accepted:true}));expect(count).toBe(1);
});

it('reuses the exact request and key after an uncertain save and route remount',async()=>{
  const read=async()=>latest,save=vi.fn<Save>().mockRejectedValue(new Error('Synthetic uncertain result'));
  const view=render(<Root read={read} save={save}/>);fireEvent.change(screen.getByLabelText('Title'),{target:{value:'Retry retained title'}});
  fireEvent.click(screen.getByRole('button',{name:'Preview'}));await screen.findByText('Synthetic uncertain result');
  view.rerender(<Root read={read} save={save} show={false}/>);view.rerender(<Root read={read} save={save}/>);
  fireEvent.click(screen.getByRole('button',{name:'Preview'}));await waitFor(()=>expect(save).toHaveBeenCalledTimes(2));
  expect(save.mock.calls[1]).toEqual(save.mock.calls[0]);
});

it('keeps a late acknowledgement and error within their original actor scope',async()=>{
  let reject!:(value:Error)=>void;
  const read=async()=>latest,save=vi.fn<Save>(()=>new Promise((_resolve,fail)=>{reject=fail;}));
  const view=render(<Root read={read} save={save}/>);fireEvent.change(screen.getByLabelText('Title'),{target:{value:'Owner A submitted'}});
  fireEvent.click(screen.getByRole('button',{name:'Preview'}));await waitFor(()=>expect(save).toHaveBeenCalledTimes(1));
  view.rerender(<Root actor='teacher-b' read={read} save={save}/>);
  expect(screen.getByRole('button',{name:'Preview'})).toBeEnabled();fireEvent.change(screen.getByLabelText('Title'),{target:{value:'Owner B unsaved'}});
  await act(async()=>reject(new Error('Owner A uncertain error')));
  expect(screen.getByLabelText('Title')).toHaveValue('Owner B unsaved');expect(screen.queryByText('Owner A uncertain error')).toBeNull();
  view.rerender(<Root read={read} save={save}/>);expect(screen.getByLabelText('Title')).toHaveValue('Owner A submitted');expect(screen.getByText('Owner A uncertain error')).toBeInTheDocument();
});
