import React from "react";
import "@testing-library/jest-dom/vitest";
import { act,cleanup, fireEvent, render, screen,waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PageExplanations } from "./PageExplanations";
import { ReadingInstructions } from "./ReadingInstructions";
import { SessionExitTickets } from "./ExitTickets";
import { ChatDraftActor, ChatDraftSessionProvider, chatDraftActorScope } from "../chat/route-drafts";
import type { LearningMaterial } from "../../lib/data/api/learning-gateway";
const version="00000000-0000-4000-8000-000000000002";
const materials:LearningMaterial[]=[{id:"material",offering_id:"offering",title:"Synthetic source",description:"",visibility:"VISIBLE",revision:1,
  current_published_version_id:version,versions:[{id:version,version_no:1,processing_state:"READY",publication_state:"PUBLISHED",page_count:3,has_text_layer:true,revision:1}]}];
function Root({kind,open=true,session="session-a",account="teacher",roles=["LECTURER"]}:{kind:"instruction"|"explanation";open?:boolean;session?:string;account?:string;roles?:string[]}){
  return <ChatDraftSessionProvider><ChatDraftActor value={chatDraftActorScope({user_id:account,roles})}>
    {open&&(kind==="instruction"?<ReadingInstructions key={session+account} actorId={account} sessionId={session} materials={materials} canManage onOpen={()=>{}}/>
      :<PageExplanations key={session+account} actorId={account} sessionId={session} materials={materials} canManage onPublish={async()=>{}} onOpen={()=>{}}/>)}
  </ChatDraftActor></ChatDraftSessionProvider>;
}
afterEach(()=>{cleanup();vi.restoreAllMocks();});
it.each(["instruction","explanation"] as const)("retains the unsent %s draft across a route unmount",async kind=>{
  const fetcher=vi.spyOn(globalThis,"fetch").mockImplementation(async()=>new Response(JSON.stringify({items:[]})));
  const instance=render(<Root kind={kind}/>);
  const source=kind==="instruction"?"Tài liệu":"Phiên bản nguồn";
  const field=kind==="instruction"?"Mục đích":"Nội dung lời giải";
  fireEvent.change(screen.getByLabelText(source),{target:{value:version}});
  fireEvent.change(screen.getByLabelText(field),{target:{value:"Private unsent instructor prose"}});
  if(kind==="instruction")fireEvent.change(screen.getByLabelText("Trang cần đọc"),{target:{value:"1-2"}});
  instance.rerender(<Root kind={kind} open={false}/>);instance.rerender(<Root kind={kind}/>);
  expect(screen.getByLabelText(field)).toHaveValue("Private unsent instructor prose");
  expect(screen.getByLabelText(source)).toHaveValue(version);
  expect(fetcher.mock.calls.some(([,init])=>init?.method&&init.method!=="GET")).toBe(false);
});

it.each(["instruction","explanation"] as const)("isolates %s drafts by session, actor and roles",kind=>{
  vi.spyOn(globalThis,"fetch").mockImplementation(async()=>new Response(JSON.stringify({items:[]})));
  const instance=render(<Root kind={kind}/>);
  const field=kind==="instruction"?"Mục đích":"Nội dung lời giải";
  fireEvent.change(screen.getByLabelText(field),{target:{value:"Original private instructor draft"}});
  for(const changed of [{session:"session-b"},{account:"teacher-b"},{roles:["SYSTEM_ADMIN"]}]){
    instance.rerender(<Root kind={kind} {...changed}/>);
    expect(screen.getByLabelText(field)).toHaveValue("");
    instance.rerender(<Root kind={kind}/>);
    expect(screen.getByLabelText(field)).toHaveValue("Original private instructor draft");
  }
});

it.each(["instruction","explanation"] as const)("keeps the %s request key for an explicit retry after unmount",async kind=>{
  const keys:string[]=[];
  vi.spyOn(globalThis,"fetch").mockImplementation(async(_input,init)=>{
    if(init?.method==="POST"){
      keys.push(new Headers(init.headers).get("Idempotency-Key")!);
      if(keys.length===1)throw new TypeError("Synthetic lost response");
      return new Response(JSON.stringify({}));
    }
    return new Response(JSON.stringify({items:[]}));
  });
  const instance=render(<Root kind={kind}/>);
  fireEvent.change(screen.getByLabelText(kind==="instruction"?"Tài liệu":"Phiên bản nguồn"),{target:{value:version}});
  fireEvent.change(screen.getByLabelText(kind==="instruction"?"Mục đích":"Nội dung lời giải"),{target:{value:"Uncertain instructor save"}});
  if(kind==="instruction")fireEvent.change(screen.getByLabelText("Trang cần đọc"),{target:{value:"1-2"}});
  const button=kind==="instruction"?"Lưu chỉ dẫn":"Lưu bản nháp lời giải";
  fireEvent.click(screen.getByRole("button",{name:button}));await screen.findByRole("alert");
  instance.rerender(<Root kind={kind} open={false}/>);instance.rerender(<Root kind={kind}/>);
  fireEvent.click(screen.getByRole("button",{name:button}));
  await waitFor(()=>expect(keys).toHaveLength(2));expect(keys[1]).toBe(keys[0]);
});

it.each(["instruction","explanation"] as const)("preserves a newer %s edit when the previous lifetime's save resolves",async kind=>{
  let finish!:()=>void;
  vi.spyOn(globalThis,"fetch").mockImplementation(async(_input,init)=>init?.method==="POST"?new Promise(resolve=>{finish=()=>resolve(new Response(JSON.stringify({})));}):new Response(JSON.stringify({items:[]})));
  const instance=render(<Root kind={kind}/>);
  const field=kind==="instruction"?"Mục đích":"Nội dung lời giải";
  fireEvent.change(screen.getByLabelText(kind==="instruction"?"Tài liệu":"Phiên bản nguồn"),{target:{value:version}});
  fireEvent.change(screen.getByLabelText(field),{target:{value:"Earlier submitted draft"}});
  if(kind==="instruction")fireEvent.change(screen.getByLabelText("Trang cần đọc"),{target:{value:"1-2"}});
  fireEvent.click(screen.getByRole("button",{name:kind==="instruction"?"Lưu chỉ dẫn":"Lưu bản nháp lời giải"}));
  await waitFor(()=>expect(finish).toBeTypeOf("function"));
  instance.rerender(<Root kind={kind} open={false}/>);instance.rerender(<Root kind={kind}/>);
  fireEvent.change(screen.getByLabelText(field),{target:{value:"Newer unsent instructor draft"}});
  await act(async()=>finish());expect(screen.getByLabelText(field)).toHaveValue("Newer unsent instructor draft");
});

it("restores the open exit-ticket composer and its unsent source/question after a route unmount",()=>{
  vi.spyOn(globalThis,"fetch").mockImplementation(async()=>new Response(JSON.stringify({items:[]})));
  function Tickets({open=true}:{open?:boolean}){return <ChatDraftSessionProvider><ChatDraftActor value={chatDraftActorScope({user_id:"teacher",roles:["LECTURER"]})}>
    {open&&<SessionExitTickets actorId="teacher" sessionId="session-a" materials={materials} instructions={[]} zoneId="Asia/Bangkok" canManage refresh={0} onRows={()=>{}} onSelect={()=>{}}/>}
  </ChatDraftActor></ChatDraftSessionProvider>;}
  const instance=render(<Tickets/>);
  fireEvent.click(screen.getByRole("button",{name:"Tạo phiếu ra lớp"}));
  fireEvent.change(screen.getByLabelText("Phiên bản nguồn"),{target:{value:version}});
  fireEvent.change(screen.getByLabelText("Câu hỏi vận dụng"),{target:{value:"Unsent source-bound exit question"}});
  instance.rerender(<Tickets open={false}/>);instance.rerender(<Tickets/>);
  expect(screen.getByLabelText("Câu hỏi vận dụng")).toHaveValue("Unsent source-bound exit question");
  expect(screen.getByLabelText("Phiên bản nguồn")).toHaveValue(version);
});

function TicketRoot({open=true,onSelect=()=>{}}:{open?:boolean;onSelect?:(id:string)=>void}){
  return <ChatDraftSessionProvider><ChatDraftActor value={chatDraftActorScope({user_id:"teacher",roles:["LECTURER"]})}>
    {open&&<SessionExitTickets actorId="teacher" sessionId="session-a" materials={materials} instructions={[]} zoneId="Asia/Bangkok" canManage refresh={0} onRows={()=>{}} onSelect={onSelect}/>}
  </ChatDraftActor></ChatDraftSessionProvider>;
}
function prepareTicket(){
  fireEvent.click(screen.getByRole("button",{name:"Tạo phiếu ra lớp"}));
  fireEvent.change(screen.getByLabelText("Phiên bản nguồn"),{target:{value:version}});
  fireEvent.change(screen.getByLabelText("Câu hỏi vận dụng"),{target:{value:"Unsent original exit question"}});
  fireEvent.change(screen.getByLabelText("Giờ mở (Asia/Bangkok)"),{target:{value:"2026-11-12T09:00"}});
  fireEvent.change(screen.getByLabelText("Giờ đóng (Asia/Bangkok)"),{target:{value:"2026-11-12T10:00"}});
}
it("retains an in-flight create, unlocks after remount and starts the next ticket empty",async()=>{
  let finish!:()=>void;
  const ticket={id:"00000000-0000-4000-8000-000000000099",state:"DRAFT",question:"Unsent original exit question",page_no:1};
  let created=false;
  vi.spyOn(globalThis,"fetch").mockImplementation(async(_input,init)=>init?.method==="POST"?new Promise(resolve=>{finish=()=>{created=true;resolve(new Response(JSON.stringify(ticket)));};}):new Response(JSON.stringify({items:created?[ticket]:[]})));
  const select=vi.fn();const instance=render(<TicketRoot onSelect={select}/>);prepareTicket();
  fireEvent.click(screen.getByRole("button",{name:"Lưu bản nháp"}));await waitFor(()=>expect(finish).toBeTypeOf("function"));
  instance.rerender(<TicketRoot open={false} onSelect={select}/>);instance.rerender(<TicketRoot onSelect={select}/>);
  expect(screen.getByLabelText("Câu hỏi vận dụng")).toBeDisabled();
  expect(screen.getByLabelText("Câu hỏi vận dụng")).toHaveValue("Unsent original exit question");
  await act(async()=>finish());
  await screen.findByRole("button",{name:ticket.question});expect(select).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button",{name:"Tạo phiếu ra lớp"}));
  expect(screen.getByLabelText("Câu hỏi vận dụng")).toHaveValue("");expect(screen.getByLabelText("Câu hỏi vận dụng")).toBeEnabled();
});

it("retains an uncertain ticket payload and exact idempotency key after route unmount",async()=>{
  const keys:string[]=[];const payloads:unknown[]=[];
  vi.spyOn(globalThis,"fetch").mockImplementation(async(_input,init)=>{
    if(init?.method==="POST"){
      keys.push(new Headers(init.headers).get("Idempotency-Key")!);payloads.push(JSON.parse(String(init.body)));
      if(keys.length===1)throw new TypeError("Synthetic uncertain ticket response");
      return new Response(JSON.stringify({id:"00000000-0000-4000-8000-000000000099",state:"DRAFT",question:"Saved exit question",page_no:1}));
    }
    return new Response(JSON.stringify({items:[]}));
  });
  const instance=render(<TicketRoot/>);prepareTicket();fireEvent.click(screen.getByRole("button",{name:"Lưu bản nháp"}));
  await screen.findByRole("alert");instance.rerender(<TicketRoot open={false}/>);instance.rerender(<TicketRoot/>);
  expect(screen.getByLabelText("Câu hỏi vận dụng")).toHaveValue("Unsent original exit question");
  fireEvent.click(screen.getByRole("button",{name:"Lưu bản nháp"}));await waitFor(()=>expect(keys).toHaveLength(2));
  expect(keys[1]).toBe(keys[0]);expect(payloads[1]).toEqual(payloads[0]);
});
