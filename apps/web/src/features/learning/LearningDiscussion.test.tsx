import React from "react";
import { afterEach,describe,expect,it,vi } from "vitest";
import { cleanup,fireEvent,render,screen,waitFor,within } from "@testing-library/react";
import { LearningDiscussion } from "./LearningDiscussion";
const methods=vi.hoisted(()=>({list:vi.fn(),write:vi.fn()}));
vi.mock("../../lib/data/api/learning-gateway",()=>({LearningGateway:class{list=methods.list;write=methods.write;}}));
afterEach(()=>{cleanup();vi.clearAllMocks();});
const version="019a0000-0000-7000-8000-000000000001";
const selection={version_id:version,page_no:2,anchor:{kind:"PAGE" as const}};
describe("learning discussion source and visibility",()=>{
  it("defaults a new question to private to current instructors and preserves the anchor",async()=>{
    methods.list.mockResolvedValue([]);methods.write.mockResolvedValue({});
    render(<LearningDiscussion versionId={version} selection={selection} canManage={false} onAnnotationsChange={()=>{}}/>);
    await waitFor(()=>expect(methods.list).toHaveBeenCalledTimes(2));
    expect((screen.getByLabelText("Ai được xem") as HTMLSelectElement).value).toBe("PRIVATE_TO_INSTRUCTORS");
    fireEvent.change(screen.getByLabelText("Câu hỏi"),{target:{value:"Tại sao kết quả này?"}});
    fireEvent.click(screen.getByRole("button",{name:"Gửi câu hỏi"}));
    await waitFor(()=>expect(methods.write).toHaveBeenCalledWith(`/versions/${version}/questions`,expect.objectContaining({page_no:2,anchor:{kind:"PAGE"},visibility:"PRIVATE_TO_INSTRUCTORS",body:"Tại sao kết quả này?"}),"POST",expect.any(String)));
  });
  it("does not offer a teacher endorsement action to a student",async()=>{
    methods.list.mockImplementation(async(path:string)=>path.includes("questions")?[{id:"q1",page_no:2,body:"Question",visibility:"CLASS",replies:[{id:"r1",body:"Reply",author_name:"Student",endorsed:false}]}]:[]);
    render(<LearningDiscussion versionId={version} selection={null} canManage={false} onAnnotationsChange={()=>{}}/>);
    await screen.findByText("Reply");expect(screen.queryByRole("button",{name:"Xác nhận câu trả lời"})).toBeNull();
    expect((screen.getByRole("button",{name:"Lưu ghi chú riêng"}) as HTMLButtonElement).disabled).toBe(true);
  });
  it("binds a PowerPoint note to the exact rendition being displayed",async()=>{
    methods.list.mockResolvedValue([]);methods.write.mockResolvedValue({});
    const rendition='019a0000-0000-7000-8000-000000000002';
    render(<LearningDiscussion versionId={version} renditionId={rendition} selection={selection} canManage={false} onAnnotationsChange={()=>{}}/>);
    await waitFor(()=>expect(methods.list).toHaveBeenCalledTimes(2));
    fireEvent.change(screen.getByLabelText('Nội dung ghi chú'),{target:{value:'Note on converted slide'}});
    fireEvent.click(screen.getByRole('button',{name:'Lưu ghi chú riêng'}));
    await waitFor(()=>expect(methods.write).toHaveBeenCalledWith('/me/annotations',expect.objectContaining({version_id:version,rendition_id:rendition,page_no:2}),"POST",expect.any(String)));
  });
  it("renders note text as text rather than executable markup",async()=>{
    methods.list.mockImplementation(async(path:string)=>path.includes("annotations")?[{id:"n1",version_id:version,page_no:2,anchor:{kind:"PAGE"},body:'<script>alert(1)</script>',revision:1,status:"ACTIVE"}]:[]);
    const {container}=render(<LearningDiscussion versionId={version} selection={null} canManage={false} onAnnotationsChange={()=>{}}/>);
    await screen.findByText('<script>alert(1)</script>');expect(container.querySelector("script")).toBeNull();
  });
  it("opens the source page and only shares after reviewing the exact content",async()=>{
    const source=vi.fn();
    const thread={id:"q1",page_no:2,body:"Vì sao kết quả này xuất hiện?",visibility:"PRIVATE_TO_INSTRUCTORS",author_id:"student",revision:4,replies:[]};
    methods.list.mockImplementation(async(path:string)=>path.includes("questions")?[thread]:[]);
    methods.write.mockResolvedValue({preview_id:"preview",confirmation_token:"token",sharing:{from:thread.visibility,to:"CLASS",version_id:version,body:thread.body,page_no:2,anchor:{kind:"PAGE"}}});
    render(<LearningDiscussion versionId={version} selection={null} canManage={false} actorId="student" onSource={source} onAnnotationsChange={()=>{}}/>);
    fireEvent.click(await screen.findByRole("button",{name:"Mở trang 2 của câu hỏi"}));
    expect(source).toHaveBeenCalledWith(2);
    fireEvent.click(screen.getByRole("button",{name:"Xem trước khi chia sẻ với lớp"}));
    const dialog=await screen.findByRole("dialog",{name:"Xác nhận phạm vi câu hỏi"});
    expect(within(dialog).getByText(thread.body)).toBeTruthy();
    const confirm=within(dialog).getByRole("button",{name:"Xác nhận đổi phạm vi"}) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    expect(methods.write).toHaveBeenCalledTimes(1);
    fireEvent.click(within(dialog).getByRole("checkbox"));
    await waitFor(()=>expect(confirm.disabled).toBe(false));
    fireEvent.click(confirm);
    await waitFor(()=>expect(methods.write).toHaveBeenCalledWith("/questions/q1",{visibility:"CLASS",revision:4,preview_id:"preview",confirmation_token:"token"},"PATCH","learning-question:preview"));
  });
});
