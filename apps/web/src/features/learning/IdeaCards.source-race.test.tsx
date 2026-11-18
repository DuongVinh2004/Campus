import React from "react";
import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { IdeaCards } from "./IdeaCards";
import { ChatDraftActor, ChatDraftSessionProvider, chatDraftActorScope } from "../chat/route-drafts";
const actorId = "00000000-0000-4000-8000-000000000008";
const version = "00000000-0000-4000-8000-000000000006";
const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
const source = (page: number) => ({ sequence: page, selection: { version_id: version, page_no: page, anchor: { kind: "PAGE" as const } } });
const view = (page: number) => <IdeaCards actorId={actorId} canCreate sourceRequest={source(page)} onOpen={() => {}} onShare={async () => {}} />;
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
it("keeps the newly selected source editor open when an earlier source save completes", async () => {
  let finish!: () => void;
  const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    if (String(input) === "/v1/learning/me/idea-cards" && init?.method === "POST")
      return new Promise(resolve => { finish = () => resolve(json({})); });
    return json({ items: [] });
  });
  const instance = render(view(1));
  for (const name of ["Vấn đề", "Ý tưởng", "Cách kiểm chứng"]) fireEvent.change(screen.getByLabelText(name), { target: { value: "Submitted prose for page one" } });
  fireEvent.click(screen.getByRole("button", { name: "Lưu phiếu ý tưởng" }));
  await waitFor(() => expect(finish).toBeTypeOf("function"));
  instance.rerender(view(2));
  expect(screen.getByText(/Nguồn · Trang 2/)).toBeVisible();
  await act(async () => finish());
  expect(screen.getByRole("heading", { name: "Lưu phiếu riêng" })).toBeVisible();
  expect(screen.getByText(/Nguồn · Trang 2/)).toBeVisible();
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
});

it("restores independent prose for two source pages without making a write", () => {
  const fetcher=vi.spyOn(globalThis,"fetch").mockImplementation(async()=>json({items:[]}));
  const instance=render(view(1));
  fireEvent.change(screen.getByLabelText("Ý tưởng"),{target:{value:"Unsent page one idea"}});
  instance.rerender(view(2));
  expect(screen.getByLabelText("Ý tưởng")).toHaveValue("");
  fireEvent.change(screen.getByLabelText("Ý tưởng"),{target:{value:"Unsent page two idea"}});
  instance.rerender(view(1));
  expect(screen.getByLabelText("Ý tưởng")).toHaveValue("Unsent page one idea");
  expect(fetcher.mock.calls.some(([,init])=>init?.method==="POST")).toBe(false);
});

it("retains prose across a route unmount in the original verified account scope", () => {
  vi.spyOn(globalThis,"fetch").mockImplementation(async()=>json({items:[]}));
  function Root({open=true,account=actorId}:{open?:boolean;account?:string}){
    return <ChatDraftSessionProvider><ChatDraftActor value={chatDraftActorScope({user_id:account,roles:["STUDENT"]})}>
      {open&&view(1)}</ChatDraftActor></ChatDraftSessionProvider>;
  }
  const instance=render(<Root/>);
  fireEvent.change(screen.getByLabelText("Ý tưởng"),{target:{value:"Private retained idea"}});
  instance.rerender(<Root open={false}/>);instance.rerender(<Root account="different-account"/>);
  expect(screen.getByLabelText("Ý tưởng")).toHaveValue("");
  instance.rerender(<Root open={false}/>);instance.rerender(<Root/>);
  expect(screen.getByLabelText("Ý tưởng")).toHaveValue("Private retained idea");
});

it.each([false,true])("preserves the uncertain save key across route unmount (changed body: %s)",async changed=>{
  const keys:string[]=[];
  vi.spyOn(globalThis,"fetch").mockImplementation(async(input,init)=>{
    if(String(input)==="/v1/learning/me/idea-cards"&&init?.method==="POST"){
      keys.push(new Headers(init.headers).get("Idempotency-Key")!);
      if(keys.length===1)throw new TypeError("Synthetic lost response");
      return json({});
    }
    return json({items:[]});
  });
  function Root({open=true}:{open?:boolean}){return <ChatDraftSessionProvider><ChatDraftActor value={chatDraftActorScope({user_id:actorId,roles:["STUDENT"]})}>{open&&view(1)}</ChatDraftActor></ChatDraftSessionProvider>;}
  const instance=render(<Root/>);
  for(const name of ["Vấn đề","Ý tưởng","Cách kiểm chứng"])fireEvent.change(screen.getByLabelText(name),{target:{value:"Uncertain submitted prose"}});
  fireEvent.click(screen.getByRole("button",{name:"Lưu phiếu ý tưởng"}));
  await screen.findByRole("alert");
  instance.rerender(<Root open={false}/>);instance.rerender(<Root/>);
  if(changed)fireEvent.change(screen.getByLabelText("Ý tưởng"),{target:{value:"Explicitly changed prose"}});
  fireEvent.click(screen.getByRole("button",{name:"Lưu phiếu ý tưởng"}));
  await waitFor(()=>expect(keys).toHaveLength(2));
  if(changed)expect(keys[1]).not.toBe(keys[0]);else expect(keys[1]).toBe(keys[0]);
  await waitFor(()=>expect(screen.queryByRole("heading",{name:"Lưu phiếu riêng"})).toBeNull());
});

it("retains the unsent topic title across route unmount without a POST",()=>{
  const fetcher=vi.spyOn(globalThis,"fetch").mockImplementation(async()=>json({items:[]}));
  function Root({open=true}:{open?:boolean}){return <ChatDraftSessionProvider><ChatDraftActor value={chatDraftActorScope({user_id:actorId,roles:["STUDENT"]})}>{open&&view(1)}</ChatDraftActor></ChatDraftSessionProvider>;}
  const instance=render(<Root/>);
  fireEvent.change(screen.getByLabelText("Tên đề tài"),{target:{value:"Unsent topic title"}});
  instance.rerender(<Root open={false}/>);instance.rerender(<Root/>);
  expect(screen.getByLabelText("Tên đề tài")).toHaveValue("Unsent topic title");
  expect(fetcher.mock.calls.some(([,init])=>init?.method==="POST")).toBe(false);
});
