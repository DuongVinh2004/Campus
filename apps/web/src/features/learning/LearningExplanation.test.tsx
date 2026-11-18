import React from "react";
import { afterEach,describe,expect,it,vi } from "vitest";
import { cleanup,fireEvent,render,screen,waitFor,act } from "@testing-library/react";
import { LearningExplanation } from "./LearningExplanation";
const methods=vi.hoisted(()=>({write:vi.fn()}));
vi.mock("../../lib/data/api/learning-gateway",()=>({LearningGateway:class{write=methods.write;}}));
afterEach(()=>{cleanup();vi.clearAllMocks();});
const version="019a0000-0000-7000-8000-000000000001",other="019a0000-0000-7000-8000-000000000002";
const selection={version_id:version,page_no:2,anchor:{kind:"PAGE" as const}};
describe("learning explanation availability and source",()=>{
  it("does not offer a provider request when capability is unavailable",()=>{
    render(<LearningExplanation versionId={version} selection={selection} available={false} onSource={()=>{}}/>);
    expect(screen.queryByRole("button",{name:"Giải thích nội dung"})).toBeNull();expect(methods.write).not.toHaveBeenCalled();
  });
  it("refuses a response citing a different source version",async()=>{
    methods.write.mockResolvedValue({answer:"Wrong source",questions:[],citations:[{version_id:other,page_no:2}]});
    render(<LearningExplanation versionId={version} selection={selection} available onSource={()=>{}}/>);
    fireEvent.click(screen.getByRole("button",{name:"Giải thích nội dung"}));await screen.findByText("Chưa xác minh được nguồn của câu trả lời.");expect(screen.queryByText("Wrong source")).toBeNull();
  });
  it("does not display a late answer after navigating to another version",async()=>{
    let resolve!:(value:unknown)=>void;methods.write.mockReturnValue(new Promise(done=>{resolve=done;}));
    const {rerender}=render(<LearningExplanation versionId={version} selection={selection} available onSource={()=>{}}/>);
    fireEvent.click(screen.getByRole("button",{name:"Giải thích nội dung"}));await waitFor(()=>expect(methods.write).toHaveBeenCalled());
    rerender(<LearningExplanation versionId={other} selection={null} available onSource={()=>{}}/>);
    await act(async()=>resolve({answer:"Old answer",questions:[],citations:[{version_id:version,page_no:2}]}));expect(screen.queryByText("Old answer")).toBeNull();
  });
});
