import React from "react";
import { afterEach,beforeEach,describe,expect,it,vi } from "vitest";
import { act,cleanup,fireEvent,render,screen,waitFor } from "@testing-library/react";
import { LearningWorkspace } from "./LearningWorkspace";
import { ChangeDetails } from "./VersionChanges";
import { LearningApiError } from "../../lib/data/api/learning-gateway";
import type { ReaderState } from "./reader/LearningPdfReader";
const api=vi.hoisted(()=>({capabilities:vi.fn(),offerings:vi.fn(),sessions:vi.fn(),sessionContexts:vi.fn(),materials:vi.fn(),reader:vi.fn(),list:vi.fn(),write:vi.fn(),request:vi.fn(),preview:vi.fn()}));
vi.mock("../../lib/data/api/learning-gateway",()=>({LearningGateway:class{capabilities=api.capabilities;offerings=api.offerings;sessions=api.sessions;sessionContexts=api.sessionContexts;materials=api.materials;reader=api.reader;list=api.list;write=api.write;request=api.request;preview=api.preview;},LearningApiError:class extends Error{status=409;}}));
vi.mock("../../components/AppShell",()=>({AppShell:({children}:{children:React.ReactNode})=><div>{children}</div>}));
vi.mock("./reader/LearningPdfReader",()=>({
  LearningPdfReader: ({version,onStateChange}: {
    version: {title:string}; onStateChange: (state: ReaderState) => void;
  }) => <div aria-label="Reader stub">{version.title}
    {[2, 3].map(page => <button key={page} onClick={() => onStateChange({
      page_no: page, offset_x: 0, offset_y: 0, scroll_mode: "vertical",
      zoom_mode: "page-width", zoom_value: 1, rotation: 0,
    })}>Đọc trang {page}</button>)}
  </div>,
}));
vi.mock("./LearningDiscussion",()=>({LearningDiscussion:()=>null}));
vi.mock("./ReadingInstructions",()=>({ReadingInstructions:()=>null}));
const offeringId="019a0000-0000-7000-8000-000000000001",sessionId="019a0000-0000-7000-8000-000000000002",versionId="019a0000-0000-7000-8000-000000000003";
const readerActor = "019a0000-0000-7000-8000-000000000004";
const offering={id:offeringId,title:"Lớp CSDL",status:"ACTIVE",revision:1,capabilities:{read:true,manage:false}};
beforeEach(()=>{
  vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({roles:["STUDENT"],user_id:readerActor}))));
  api.capabilities.mockResolvedValue({available:true});api.offerings.mockResolvedValue([offering]);api.sessions.mockResolvedValue([{id:sessionId,title:"Buổi một",sequence_no:1,description:"",starts_at:null,revision:1}]);
  api.materials.mockResolvedValue([{id:offeringId,title:"Bài giảng SQL",description:"",visibility:"VISIBLE",current_published_version_id:versionId,revision:1,versions:[{id:versionId,version_no:1,processing_state:"READY",publication_state:"PUBLISHED"}]}]);
  api.list.mockResolvedValue([]);api.request.mockResolvedValue({revision:0,page_no:1});api.reader.mockResolvedValue({id:versionId,version_id:versionId,title:"Bài giảng SQL",content_path:`/v1/learning/versions/${versionId}/content`,page_count:4,capabilities:{download:true,manage:false}});
});
afterEach(()=>{cleanup();window.history.replaceState(null,"","/");vi.clearAllMocks();vi.unstubAllGlobals();});
describe("learning workspace authorization and publication",()=>{
  it("rechecks the session before loading classes after an initial service failure", async () => {
    const fetcher = vi.mocked(fetch);
    fetcher.mockResolvedValueOnce(new Response("{}", { status: 503 }));
    render(<LearningWorkspace />);
    await screen.findByText("Chưa kiểm tra được phiên đăng nhập.");
    expect(api.offerings).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Tải lại" }));
    await screen.findByText("Bài giảng SQL");
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(api.capabilities).toHaveBeenCalledTimes(1);
  });
  it("lets a student browse published material without teacher controls",async()=>{
    render(<LearningWorkspace/>);await screen.findByText("Bài giảng SQL");
    expect(screen.queryByRole("button",{name:"Thêm buổi"})).toBeNull();
    expect(screen.queryByRole("button",{name:"Công bố"})).toBeNull();
    fireEvent.click(screen.getByRole("button",{name:"Đọc bài giảng"}));
    await screen.findByLabelText("Reader stub");expect(api.reader).toHaveBeenCalledWith(versionId);
  });
  it("requires preview and a checked confirmation before an admin creates a course",async()=>{
    vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({roles:["SYSTEM_ADMIN"]}))));
    api.write.mockImplementation(async(path:string)=>path==="/action-previews"?{preview_id:versionId,confirmation_token:"test",expires_at:"2099-01-01T00:00:00Z",payload:{code:"C1",name:"Môn mới"}}:{id:versionId});
    render(<LearningWorkspace/>);const summary=await screen.findByText("Quản trị học kỳ, môn học và thành viên");fireEvent.click(summary);
    await waitFor(()=>expect(api.list).toHaveBeenCalledWith("/terms",expect.any(AbortSignal)));
    await waitFor(()=>expect((screen.getByRole("button",{name:"Tạo môn học"}) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.change(screen.getByLabelText("Mã môn"),{target:{value:"C1"}});fireEvent.change(screen.getByLabelText("Tên môn"),{target:{value:"Môn mới"}});
    fireEvent.click(screen.getByRole("button",{name:"Tạo môn học"}));
    const confirm=await screen.findByRole("button",{name:"Xác nhận thay đổi"});expect((confirm as HTMLButtonElement).disabled).toBe(true);
    expect(api.write.mock.calls.filter(([path])=>path==="/courses")).toHaveLength(0);
    fireEvent.click(screen.getByLabelText("Tôi đã kiểm tra thông tin và tác động."));fireEvent.click(confirm);
    await waitFor(()=>expect(api.write).toHaveBeenCalledWith("/courses",expect.objectContaining({code:"C1",name:"Môn mới",preview_id:versionId,confirmation_token:"test"}),"POST",`learning-action:${versionId}`));
  });
  it("does not load class data when capability is unavailable",async()=>{
    api.capabilities.mockResolvedValue({available:false});render(<LearningWorkspace/>);
    await screen.findByText("Dịch vụ học liệu chưa được bật hoặc chưa sẵn sàng.");expect(api.offerings).not.toHaveBeenCalled();
  });
  it("shows the exact class explanation in the publication preview before confirming", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ roles: ["LECTURER"], user_id: readerActor }))));
    api.offerings.mockResolvedValue([{ ...offering, capabilities: { read: true, manage: true, page_explanations: true } }]);
    const draft = { id: versionId, session_id: sessionId, version_id: versionId, page_no: 3,
      body: "Ví dụ chung đã lưu", category: "ADD_EXAMPLE", status: "DRAFT", revision: 2, published_at: null };
    api.list.mockImplementation(async (path: string) => path.endsWith("/page-explanations") ? [draft] : []);
    api.write.mockImplementation(async (path: string) => path === "/action-previews"
      ? { preview_id: versionId, confirmation_token: "synthetic", page_explanation: draft }
      : { ...draft, status: "PUBLISHED" });
    render(<LearningWorkspace />);
    fireEvent.click(await screen.findByRole("button", { name: "Xem trước công bố" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog.textContent).toContain("Ví dụ chung đã lưu");
    expect(dialog.textContent).toContain("Trang 3");
    expect(api.write).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByLabelText("Tôi đã kiểm tra thông tin và tác động."));
    fireEvent.click(screen.getByRole("button", { name: "Xác nhận thay đổi" }));
    await waitFor(() => expect(api.write).toHaveBeenCalledWith(
      `/page-explanations/${versionId}`,
      { revision: 2, publish: true, preview_id: versionId, confirmation_token: "synthetic" },
      "PATCH", `learning-action:${versionId}`,
    ));
  });
  it("opens the two distinct version anchors for a moved PDF page and a PowerPoint slide", () => {
    const open = vi.fn();
    const target = "019a0000-0000-7000-8000-000000000007";
    render(<ChangeDetails change={{
      revision: 1, mode: "PAGE_MAP", target_version_id: target, target_version_no: 2,
      target_media_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
      target_guidance: "", base_available: true, base_version_id: versionId, base_version_no: 1,
      base_media_type: "application/pdf", items: [{ kind: "MOVED", old_page: 4, new_page: 8, description: "Di chuyển trang" }],
    }} onOpen={open} />);
    fireEvent.click(screen.getByRole("button", { name: "Mở bản trước · Trang PDF 4" }));
    fireEvent.click(screen.getByRole("button", { name: "Mở bản mới · Slide trong bản xem PowerPoint 8" }));
    expect(open.mock.calls).toEqual([[versionId, 4], [target, 8]]);
  });
  it("opens an exit ticket notice in the correct class and session before opening its exact source", async () => {
    const nextOffering = "019a0000-0000-7000-8000-000000000009";
    const nextSession = "019a0000-0000-7000-8000-000000000010";
    const targetTicket = "019a0000-0000-7000-8000-000000000011";
    const note = "019a0000-0000-7000-8000-000000000012";
    api.offerings.mockResolvedValue([offering, { ...offering, id: nextOffering, title: "Lớp khác",
      capabilities: { ...offering.capabilities, exit_tickets: true } }]);
    api.sessions.mockImplementation(async (id: string) => id === nextOffering
      ? [{ id: nextSession, offering_id: nextOffering, title: "Buổi có phiếu", sequence_no: 1 }]
      : [{ id: sessionId, offering_id: offeringId, title: "Buổi ban đầu", sequence_no: 1 }]);
    api.list.mockImplementation(async (path: string) => path === "/me/notifications" ? [{
      id: note, event_type: "EXIT_TICKET_UPDATED", title: "Cập nhật phiếu ra lớp", exit_ticket_id: targetTicket,
      offering_id: nextOffering, session_id: nextSession, version_id: versionId, page_no: 3,
      created_at: "2026-11-05T04:00:00Z", read_at: null, revision: 1,
    }] : []);
    api.request.mockImplementation(async (path: string) => {
      if (path === `/exit-tickets/${targetTicket}`) return {
        id: targetTicket, session_id: nextSession, version_id: versionId, page_no: 3, state: "OPEN", revision: 2,
        question: "Giải thích kết quả.", zone_id: "Asia/Bangkok", instruction: null,
        opens: { local: "2026-11-05T10:00", offset_minutes: 420, utc: "2026-11-05T03:00:00Z" },
        closes: { local: "2026-11-05T11:00", offset_minutes: 420, utc: "2026-11-05T04:00:00Z" },
      };
      return path.endsWith("/me/submission") ? { submission: null } : { revision: 0, page_no: 1 };
    });
    api.write.mockResolvedValue({});
    render(<LearningWorkspace />);
    fireEvent.click(await screen.findByText(/Cập nhật học liệu · 1 chưa xem/));
    fireEvent.click(await screen.findByRole("button", { name: "Mở phiếu ra lớp" }));
    expect(await screen.findByText("Giải thích kết quả.")).toBeTruthy();
    expect((screen.getByRole("combobox", { name: "Lớp học phần" }) as HTMLSelectElement).value).toBe(nextOffering);
    expect(api.reader).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Mở trang nguồn 3" }));
    await screen.findByLabelText("Reader stub");
    expect(api.reader).toHaveBeenCalledWith(versionId);
  });
  it.each([true,false])("opens a deep link and trusts only a linked session (linked hint: %s)", async linked => {
    const secondSession = {id:"019a0000-0000-7000-8000-000000000005",offering_id:offeringId,title:"Buổi hai",sequence_no:2};
    const firstSession = {id:sessionId,offering_id:offeringId,title:"Buổi một",sequence_no:1};
    const hint = linked ? secondSession.id : "019a0000-0000-7000-8000-000000000006";
    window.history.replaceState(null,"",`/learning?version_id=${versionId}&page_no=2&session_id=${hint}`);
    api.capabilities.mockResolvedValue({available:true,session_contexts:true});
    api.reader.mockResolvedValue({id:versionId,version_id:versionId,offering_id:offeringId,title:"Bài giảng SQL",page_count:4,capabilities:{download:true,manage:false}});
    api.sessions.mockResolvedValue([firstSession,secondSession]);
    api.sessionContexts.mockResolvedValue([firstSession,secondSession]);
    render(<LearningWorkspace/>);
    await screen.findByLabelText("Reader stub");
    expect(api.sessionContexts).toHaveBeenCalledWith(versionId,expect.any(AbortSignal));
    expect(api.materials).toHaveBeenCalledWith(linked ? secondSession.id : sessionId,expect.any(AbortSignal));
  });
  it("asks for the session when a legacy link points at a reused version", async () => {
    const secondId = "019a0000-0000-7000-8000-000000000005";
    window.history.replaceState(null, "", `/learning?version_id=${versionId}&page_no=2`);
    api.capabilities.mockResolvedValue({ available: true, session_contexts: true });
    api.reader.mockResolvedValue({ id: versionId, version_id: versionId, offering_id: offeringId,
      version_no: 1, title: "Bài giảng SQL", page_count: 4, capabilities: { page_feedback: true } });
    api.sessionContexts.mockResolvedValue([
      { id: sessionId, title: "Buổi một", offering_id: offeringId, sequence_no: 1 },
      { id: secondId, title: "Buổi hai", offering_id: offeringId, sequence_no: 2 },
    ]);
    api.request.mockImplementation(async (path: string) => {
      if (path.endsWith("/me/feedback")) return { feedback: null };
      if (path.endsWith("/page-feedback-window")) return { window: { closes_at: "2099-01-01T01:00:00Z" } };
      return { revision: 0, page_no: 1 };
    });
    api.write.mockResolvedValue({ id: versionId, session_id: secondId, category: "NEED_EXAMPLE", status: "ACTIVE", revision: 1 });
    render(<LearningWorkspace />);
    fireEvent.click(await screen.findByRole("button", { name: "Em đang vướng ở trang này" }));
    const session = await screen.findByLabelText("Buổi học", { selector: "select" });
    expect((session as HTMLSelectElement).value).toBe("");
    fireEvent.change(session, { target: { value: secondId } });
    fireEvent.click(screen.getByRole("radio", { name: "Cần thêm ví dụ" }));
    const send = screen.getByRole("button", { name: "Gửi báo vướng" }) as HTMLButtonElement;
    await waitFor(() => expect(send.disabled).toBe(false));
    fireEvent.click(send);
    await screen.findByText("Đã lưu phản hồi.");
    expect(api.write).toHaveBeenCalledWith(
      `/versions/${versionId}/pages/2/me/feedback`,
      { session_id: secondId, revision: 0, category: "NEED_EXAMPLE" }, "PUT",
      expect.any(String), { "X-Campus-Reader-Actor": readerActor }, expect.any(AbortSignal),
    );
  });
  it.each(["offline", "conflict"])("retains the latest position after an older save fails with %s", async failure => {
    let rejectFirst!: (error: Error) => void;
    api.write.mockReset().mockImplementationOnce(() => new Promise((_, reject) => { rejectFirst = reject; }))
      .mockResolvedValue({ revision: 8 });
    render(<LearningWorkspace/>);
    fireEvent.click(await screen.findByRole("button",{name:"Đọc bài giảng"}));
    fireEvent.click(await screen.findByRole("button",{name:"Đọc trang 2"}));
    act(() => window.dispatchEvent(new Event("online")));
    await waitFor(() => expect(api.write).toHaveBeenCalledWith(
      `/me/reader-state/${versionId}`, expect.objectContaining({page_no:2,revision:0}), "PUT", undefined, {"X-Campus-Reader-Actor": readerActor},
    ));
    fireEvent.click(screen.getByRole("button",{name:"Đọc trang 3"}));
    await act(async () => rejectFirst(failure === "offline" ? new TypeError("Offline") : new LearningApiError(409, "REVISION_CONFLICT", "Conflict")));
    if (failure === "offline") {
      expect(await screen.findByRole("button",{name:"Thử lưu lại vị trí"})).toBeTruthy();
      act(() => window.dispatchEvent(new Event("online")));
    } else {
      api.request.mockResolvedValueOnce({revision:7,page_no:1});
      fireEvent.click(await screen.findByRole("button",{name:"Giữ vị trí trên thiết bị này"}));
    }
    await waitFor(() => expect(api.write).toHaveBeenLastCalledWith(
      `/me/reader-state/${versionId}`, expect.objectContaining({page_no:3,revision:failure === "offline" ? 0 : 7}), "PUT", undefined, {"X-Campus-Reader-Actor": readerActor},
    ));
    expect(api.write).toHaveBeenCalledTimes(2);
  });
});
