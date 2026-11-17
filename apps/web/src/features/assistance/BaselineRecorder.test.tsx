import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { BaselineRecorder, useBaselineMeasurement } from "./BaselineRecorder";

const initial = { id:"019a0000-0000-7000-8000-000000000001",version:1,case_id:"UB-04",operator_kind:"automation",state:"active",
  active_ms:0,wait_ms:0,paused_ms:0,unattributed_ms:0,counts:{},fields:{} };
function Harness({actor="student1"}:{actor?:string}) {
  const m = useBaselineMeasurement(actor);
  return <><BaselineRecorder measurement={m}/><input aria-label="Reason" onChange={() => m.markField("reason")} onBlur={() => m.flushField("reason")}/><button onClick={() => m.record("manual_action")}>Business action</button></>;
}
afterEach(() => {cleanup();vi.unstubAllGlobals();});

function setup(failEvent=false) {
  let current = {...initial};
  const calls: Array<{path:string,body:Record<string,unknown>|null}> = [];
  vi.stubGlobal("fetch",vi.fn(async (url:string,init?:RequestInit) => {
    const path = new URL(url, window.location.origin).pathname;
    const body = init?.body ? JSON.parse(init.body as string) : null;
    calls.push({path,body});
    let value:unknown;
    let status=200;
    if(path.endsWith("/cases")) value={items:[{id:"UB-04",category:"eligible_course",expected:"demo"}]};
    else if(!body && path.endsWith("/sessions")) value={items:[]};
    else if(body && path.endsWith("/sessions")) {current={...initial,operator_kind:body.operator_kind};value={session:current};status=201;}
    else if(path.endsWith("/events")) {
      if(failEvent) {status=503;value={code:"DEPENDENCY_UNAVAILABLE"};}
      else {current={...current,version:current.version+1,state:body.kind==="finish"?"finished":body.kind==="pause"?"paused":body.kind==="resume"?"active":current.state};value={session:current,receipt:{event_id:body.event_id}};}
    } else value=current;
    return new Response(JSON.stringify(value),{status});
  }));
  return calls;
}
async function begin() {
  await screen.findByRole("option",{name:"UB-04 · eligible_course"});
  fireEvent.change(screen.getByLabelText("Ca thử"),{target:{value:"UB-04"}});
  fireEvent.change(screen.getByLabelText("Loại phiên"),{target:{value:"automation"}});
  fireEvent.click(screen.getByRole("button",{name:"Bắt đầu đo"}));
  await screen.findByText(/UB-04 · Kiểm tra tự động · active/);
}

it("does not start automatically and sends no field contents",async()=>{
  const calls=setup();render(<Harness/>);
  await screen.findByRole("option",{name:"UB-04 · eligible_course"});
  expect(calls.every(c=>c.body===null)).toBe(true);
  await begin();
  fireEvent.change(screen.getByLabelText("Reason"),{target:{value:"PRIVATE CONTENT"}});
  fireEvent.blur(screen.getByLabelText("Reason"));
  await waitFor(()=>expect(calls.some(c=>c.body?.kind==="field_edit")).toBe(true));
  expect(JSON.stringify(calls)).not.toContain("PRIVATE CONTENT");
  expect(calls.find(c=>c.body?.kind==="field_edit")?.body?.field).toBe("reason");
});

it("keeps the exact event after unknown outcome and permits manual business UI",async()=>{
  const calls=setup(true);render(<Harness/>);await begin();
  fireEvent.click(screen.getByRole("button",{name:"Business action"}));
  await screen.findByRole("alert");
  const first=calls.find(c=>c.path.endsWith("/events"))!.body;
  expect(screen.getByRole("button",{name:"Business action"})).toBeEnabled();
  fireEvent.click(screen.getByRole("button",{name:"Thử lại event đang giữ"}));
  await waitFor(()=>expect(calls.filter(c=>c.path.endsWith("/events"))).toHaveLength(2));
  expect(calls.filter(c=>c.path.endsWith("/events"))[1].body).toEqual(first);
});

it("pause stops field measurement, finishing permits a new session while keeping the old one",async()=>{
  const calls=setup();render(<Harness/>);await begin();
  fireEvent.click(screen.getByRole("button",{name:"Tạm dừng đo"}));
  await screen.findByText(/ · paused · /);
  const before=calls.filter(c=>c.path.endsWith("/events")).length;
  fireEvent.change(screen.getByLabelText("Reason"),{target:{value:"unrecorded"}});fireEvent.blur(screen.getByLabelText("Reason"));
  await Promise.resolve();
  expect(calls.filter(c=>c.path.endsWith("/events"))).toHaveLength(before);
  fireEvent.click(screen.getByRole("button",{name:"Kết thúc đo"}));
  await screen.findByText(/ · finished · /);
  fireEvent.click(screen.getByRole("button",{name:"Đo phiên mới, giữ phiên cũ"}));
  expect(screen.getByRole("button",{name:"Bắt đầu đo"})).toBeInTheDocument();
  expect(screen.getByLabelText("Mở phiên gần đây")).toBeInTheDocument();
});

it("switching actors clears the old measurement projection",async()=>{
  setup();const view=render(<Harness/>);await begin();
  view.rerender(<Harness actor="student2"/>);
  await screen.findByRole("button",{name:"Bắt đầu đo"});
  expect(screen.queryByText(/Phiên đo 019a0000/)).toBeNull();
});

it("refreshes only version on explicit retry of a known stale event",async()=>{
  let attempts=0;
  const bodies: Array<Record<string,unknown>>=[];
  vi.stubGlobal("fetch",vi.fn(async(url:string,init?:RequestInit)=>{
    const path=new URL(url, window.location.origin).pathname, body=init?.body?JSON.parse(init.body as string):null;
    if(path.endsWith("/cases")) return new Response(JSON.stringify({items:[{id:"UB-04",category:"eligible_course",expected:"demo"}]}));
    if(path.endsWith("/sessions")) return new Response(JSON.stringify(body?{session:initial}:{items:[]}),{status:body?201:200});
    if(path.endsWith("/events")) {
      bodies.push(body);attempts++;
      if(attempts===1) return new Response(JSON.stringify({code:"STALE_VERSION"}),{status:409});
      return new Response(JSON.stringify({session:{...initial,version:3,state:"paused"},receipt:{event_id:body.event_id}}));
    }
    return new Response(JSON.stringify({...initial,version:2}));
  }));
  render(<Harness/>);await begin();
  fireEvent.click(screen.getByRole("button",{name:"Tạm dừng đo"}));
  const retry=await screen.findByRole("button",{name:"Đọc phiên mới và thử lại thao tác đo"});
  fireEvent.click(retry);await screen.findByText(/ · paused · Phiên bản 3/);
  expect(bodies[1]).toEqual({...bodies[0],expected_version:2});
});
