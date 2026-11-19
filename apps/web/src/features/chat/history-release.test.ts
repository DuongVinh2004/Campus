import { describe, expect, it } from "vitest";
import { decodeHistoryPage } from "./history";

const conv="019a0000-0024-7000-8000-000000000010";
const message="019a0000-0024-7000-8000-000000000011";
function releasePage() {
  const citation={citation_id:message,source_id:conv,document_version_id:conv,chunk_id:message,
    source_title:"Contract fixture",canonical_uri:"https://example.invalid/source",version_label:"version",
    source_status:"CURRENT",locator:{section_path:"Section",page_start:2,page_end:2},quote:"Contract evidence",
    release_id:conv,release_generation:11,evidence_sha256:"a".repeat(64)};
  return {items:[{id:message,conversation_id:conv,sequence_no:2,sender_type:"ASSISTANT",content:"Contract evidence [CIT-001]",
    citations:[citation],created_at:"2026-10-23T00:00:00Z",final_result:{conversation_id:conv,message_id:message,
      status:"answered",response_class:"grounded_answer",content:"Contract evidence [CIT-001]",
      citations:[{turn_citation_id:"CIT-001",citation}]}}],page:{next_cursor:null,has_more:false}};
}
describe("release-bound history",()=>{
  it("preserves release and evidence bindings across reload",()=>{
    const restored=decodeHistoryPage(releasePage(),conv).messages[0];
    expect(restored.final?.citations[0].citation).toMatchObject({release_id:conv,release_generation:11,evidence_sha256:"a".repeat(64)});
  });
  it.each(["release_id","release_generation","evidence_sha256"])("rejects malformed %s",field=>{
    const page=releasePage();(page.items[0].final_result.citations[0].citation as Record<string,unknown>)[field]="invalid";
    expect(()=>decodeHistoryPage(page,conv)).toThrow();
  });
  it("rejects a stored citation binding that differs from the final result",()=>{
    const page=releasePage();page.items[0].citations=[{...page.items[0].citations[0],release_generation:12}];
    expect(()=>decodeHistoryPage(page,conv)).toThrow();
  });
});
