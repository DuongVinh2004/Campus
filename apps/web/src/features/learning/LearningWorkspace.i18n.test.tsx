import React from "react";
import { afterEach,beforeEach,describe,expect,it,vi } from "vitest";
import { act,cleanup,fireEvent,render,screen,waitFor } from "@testing-library/react";
import { LearningWorkspace } from "./LearningWorkspace";
import { LanguageProvider } from "../../lib/i18n";
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
  document.cookie="lang=en; path=/";
  vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({roles:["STUDENT"],user_id:readerActor}))));
  api.capabilities.mockResolvedValue({available:true});api.offerings.mockResolvedValue([offering]);api.sessions.mockResolvedValue([{id:sessionId,title:"Buổi một",sequence_no:1,description:"",starts_at:null,revision:1}]);
  api.materials.mockResolvedValue([{id:offeringId,title:"Bài giảng SQL",description:"",visibility:"VISIBLE",current_published_version_id:versionId,revision:1,versions:[{id:versionId,version_no:1,processing_state:"READY",publication_state:"PUBLISHED"}]}]);
  api.list.mockResolvedValue([]);api.request.mockResolvedValue({revision:0,page_no:1});api.reader.mockResolvedValue({id:versionId,version_id:versionId,title:"Bài giảng SQL",content_path:`/v1/learning/versions/${versionId}/content`,page_count:4,capabilities:{download:true,manage:false}});
});
afterEach(()=>{document.cookie="lang=; path=/; max-age=0";cleanup();window.history.replaceState(null,"","/");vi.clearAllMocks();vi.unstubAllGlobals();});
describe("learning workspace in English",()=>{
  it("translates the heading, session list and reading controls", async () => {
    render(<LanguageProvider><LearningWorkspace /></LanguageProvider>);
    expect(await screen.findByRole("heading",{name:"Learning materials by session"})).toBeInTheDocument();
    expect(await screen.findByRole("navigation",{name:"Session list"})).toBeInTheDocument();
    expect(screen.getByRole("button",{name:"Reload"})).toBeInTheDocument();
    expect(await screen.findByText("Bài giảng SQL")).toBeInTheDocument(); // server data stays as written
    expect(screen.getByRole("button",{name:"Read the lecture"})).toBeInTheDocument();
  });
});
