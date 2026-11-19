import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { KnowledgeIntake } from "./KnowledgeIntake";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("queues a separate URL observation with the displayed original hash", async () => {
  let submitted: Record<string, unknown> | null = null;
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
    if (init?.method === "POST") { submitted = JSON.parse(String(init.body)); return new Response(JSON.stringify({ intake_id: "new-observation" }), { status: 202 }); }
    return new Response(JSON.stringify({ items: [{ id: "old-observation", filename: "url-source", state: "NEEDS_INFORMATION", stage: "METADATA_REVIEW", progress: 40,
      job_id: "job", original_sha256: "a".repeat(64), observed_at: "2026-10-27T00:00:00Z", revision: 1, hints: { source_uri: "https://huce.edu.vn/source.txt" },
      can_refresh_url: true, issues: [] }] }));
  }));
  render(<KnowledgeIntake onResolved={vi.fn()} />);
  fireEvent.click(await screen.findByRole("button", { name: "Kiểm tra lại URL, giữ bản cũ" }));
  await screen.findByText(/giữ hồ sơ cũ/);
  expect(submitted).toEqual({ expected_original_sha256: "a".repeat(64) });
});

describe("Durable intake", () => {
  it("accepts only a file without inventing metadata and retrieves it after remount", async () => {
    let accepted = false;
    let submitted: FormData | null = null;
    vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
      if (init?.method === "POST") { accepted = true; submitted = init.body as FormData;
        return new Response(JSON.stringify({ intake_id: "intake-1", job_id: "job-1" }), { status: 202 }); }
      return new Response(JSON.stringify({ items: accepted ? [{ id: "intake-1", filename: "new-source.txt", state: "QUEUED", progress: 0,
        job_id: "job-1", observed_at: "2026-10-26T00:00:00Z", issues: [], hints: {}, revision: 1 }] : [] }));
    }));
    const view = render(<KnowledgeIntake onResolved={vi.fn()} />);
    const button = await screen.findByRole("button", { name: "Tiếp nhận trước, xử lý nền" });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.change(screen.getByLabelText("Tệp tiếp nhận PDF/TXT"), { target: { files: [new File(["A completely new document."], "new-source.txt", { type: "text/plain" })] } });
    fireEvent.submit(button.closest("form")!);
    await screen.findByText(/Bạn có thể đóng trang/);
    expect(JSON.parse(String(submitted!.get("metadata")))).toEqual({ source_uri: null });
    view.unmount(); render(<KnowledgeIntake onResolved={vi.fn()} />);
    await screen.findByText("new-source.txt");
    expect(screen.getByText(/Đã tiếp nhận, chờ xử lý/)).toBeInTheDocument();
    expect(screen.queryByText(/đang sử dụng/i)).toBeNull();
  });

  it("preserves revision and does not set effectivity from upload time", async () => {
    const onResolved = vi.fn(); let submitted: Record<string, unknown> | null = null;
    vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
      if (init?.method === "POST") { submitted = JSON.parse(String(init.body)); return new Response(JSON.stringify({ version_id: "version-new" }), { status: 202 }); }
      return new Response(JSON.stringify({ items: [{ id: "intake-1", filename: "pending.txt", state: "NEEDS_INFORMATION", progress: 40,
        job_id: "job-1", observed_at: "2026-10-26T00:00:00Z", revision: 1, hints: { source_uri: "https://example.test/source" },
        issues: [{ id: "issue", code: "SOURCE_METADATA_REQUIRED", fields: ["title"], evidence: { title_candidate: "Unverified title" } }] }] }));
    }));
    render(<KnowledgeIntake onResolved={onResolved} />);
    fireEvent.click(await screen.findByRole("button", { name: "Bổ sung thông tin pending.txt" }));
    fireEvent.change(screen.getByLabelText("Đơn vị ban hành đã đối chiếu"), { target: { value: "Test publisher" } });
    fireEvent.change(screen.getByLabelText("Phạm vi chương trình"), { target: { value: "K71CS, K70CS" } });
    fireEvent.submit(screen.getByText("Lưu thông tin và chuyển sang đối chiếu").closest("form")!);
    await waitFor(() => expect(onResolved).toHaveBeenCalledWith("version-new"));
    expect(submitted).toMatchObject({ expected_revision: 1, metadata: { effective_from: null, effective_until: null, programs: ["K71CS", "K70CS"] } });
  });

  it("requires explicit source reconciliation and sends the displayed revision and release binding", async () => {
    const onResolved = vi.fn(); let submitted: Record<string, unknown> | null = null;
    vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
      if (init?.method === "POST") { submitted = JSON.parse(String(init.body)); return new Response(JSON.stringify({ version_id: "version-existing" })); }
      return new Response(JSON.stringify({ items: [{ id: "intake-duplicate", filename: "same-bytes.pdf", state: "NEEDS_INFORMATION", stage: "DUPLICATE_REVIEW", progress: 20,
        job_id: "job-duplicate", observed_at: "2026-10-26T00:00:00Z", revision: 4, hints: {}, issues: [{ id: "duplicate", code: "DUPLICATE_BYTES_CANDIDATE", fields: [],
          evidence: { generation: 27, policy_generation: 3, duplicate_candidates: [{ version_id: "version-existing", source_id: "source-existing", title: "Retained public source", canonical_uri: "https://huce.edu.vn/retained" }] } }] }] }));
    }));
    render(<KnowledgeIntake onResolved={onResolved} />);
    await screen.findByText("same-bytes.pdf");
    expect(submitted).toBeNull(); expect(onResolved).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /Bổ sung thông tin same-bytes/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Đối chiếu và liên kết bản tiếp nhận" }));
    const confirm = screen.getByRole("checkbox", { name: /Tôi đã đối chiếu cùng nhà xuất bản/ });
    expect(confirm).not.toBeChecked(); expect(confirm).toBeRequired();
    fireEvent.change(screen.getByLabelText("Căn cứ cùng nguồn và phạm vi"), { target: { value: "Confirmed the same original publisher and applicability scope." } });
    fireEvent.click(confirm);
    fireEvent.submit(screen.getByRole("button", { name: "Ghi nhận liên kết, dùng lại bằng chứng" }).closest("form")!);
    await waitFor(() => expect(onResolved).toHaveBeenCalledWith("version-existing"));
    expect(submitted).toMatchObject({ expected_revision: 4, expected_generation: 27, expected_policy_generation: 3,
      version_id: "version-existing", source_uri: "https://huce.edu.vn/retained", confirmed_same_source: true });
    await screen.findByText(/Phiên bản, ngày hiệu lực và bản phát hành giữ nguyên/);
  });

  it("shows unverified source occurrences without presenting an image as extracted facts", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.includes("/evidence?")) return new Response(JSON.stringify({ unit_count: 2, dependency_count: 0, issue_count: 1,
        offset: 0, next_offset: null, units: [{ id: "one", kind: "TEXT", verbatim: "001234 — chưa ghi tín chỉ.", locator: { page: 1, char_start: 0, char_end: 27, bbox: null } },
          { id: "two", kind: "IMAGE_REGION", verbatim: "", locator: { page: 1, char_start: null, char_end: null, bbox: [0, 0, 100, 100] } }] }));
      return new Response(JSON.stringify({ items: [{ id: "intake-evidence", filename: "diagram.pdf", state: "NEEDS_INFORMATION", stage: "METADATA_REVIEW", progress: 40,
        job_id: "job-evidence", observed_at: "2026-10-26T00:00:00Z", revision: 1, hints: {}, issues: [{ id: "metadata", code: "SOURCE_METADATA_REQUIRED", fields: [],
          evidence: { evidence_unit_count: 2 } }] }] }));
    }));
    render(<KnowledgeIntake onResolved={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Xem các đơn vị bằng chứng của diagram.pdf" }));
    await screen.findByText("001234 — chưa ghi tín chỉ.");
    expect(screen.getByText(/Nội dung và các liên kết này chưa được xác minh/)).toBeInTheDocument();
    expect(screen.getByText(/chưa có kết luận về bảng hoặc chiều mũi tên/)).toBeInTheDocument();
  });

  it("keeps local OCR separate from verified content and explains an empty result", async () => {
    vi.stubGlobal("fetch",vi.fn(async (url:string) => {
      if (url.includes("/pages/1/ocr")) return new Response(JSON.stringify({text:"",confidence:0,semantics_verified:false,admission_granted:false}));
      return new Response(JSON.stringify({items:[{id:"intake-ocr",filename:"scan.pdf",state:"NEEDS_INFORMATION",stage:"METADATA_REVIEW",progress:40,
        job_id:"job-ocr",observed_at:"2026-10-26T00:00:00Z",revision:1,hints:{},issues:[{id:"ocr",code:"SOURCE_METADATA_REQUIRED",fields:[],evidence:{ocr_pages:[1]}}]}]}));
    }));
    render(<KnowledgeIntake onResolved={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button",{name:"Xem OCR chưa xác minh trang 1"}));
    await screen.findByText(/OCR chưa đọc được chữ của trang này/);
    expect(screen.getByText(/Điểm đọc chữ không xác nhận số liệu/)).toBeInTheDocument();
  });

  it("rechecks the displayed source binding without asking to reset attempts", async () => {
    let submitted:Record<string,unknown>|null=null;
    vi.stubGlobal("fetch",vi.fn(async (_url:string,init?:RequestInit) => {
      if (init?.method === "POST") { submitted=JSON.parse(String(init.body)); return new Response(JSON.stringify({state:"QUEUED",attempts_preserved:1}),{status:202}); }
      return new Response(JSON.stringify({items:[{id:"intake-recheck",filename:"recheck.pdf",original_sha256:"a".repeat(64),state:"NEEDS_INFORMATION",stage:"METADATA_REVIEW",progress:40,
        job_id:"job-recheck",observed_at:"2026-10-26T00:00:00Z",revision:1,hints:{},issues:[]}]}));
    }));
    render(<KnowledgeIntake onResolved={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button",{name:"Kiểm lại bằng chứng và trạng thái nguồn"}));
    await screen.findByText(/giới hạn lần thử giữ nguyên/);
    expect(submitted).toEqual({expected_revision:1,expected_original_sha256:"a".repeat(64)});
  });

  it("paginates image-bound OCR occurrences while retaining the unverified explanation", async () => {
    const paths: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      paths.push(url);
      if (url.includes("/pages/1/ocr")) {
        const second = url.includes("offset=20");
        return new Response(JSON.stringify({ text: "Whole OCR page", confidence: 99, evidence: {
          unit_count: 21, dependency_count: 20, offset: second ? 20 : 0, next_offset: second ? null : 20,
          units: [{ id: second ? "last" : "first", kind: "TEXT", verbatim: second ? "Last occurrence" : "First occurrence",
            locator: { page: 1, char_start: 0, char_end: 16, bbox: [1, 2, 30, 20] } }] } }));
      }
      return new Response(JSON.stringify({ items: [{ id: "intake-ocr", filename: "scan.pdf", state: "NEEDS_INFORMATION", stage: "METADATA_REVIEW", progress: 40,
        job_id: "job-ocr", observed_at: "2026-10-26T00:00:00Z", revision: 1, hints: {}, issues: [{ id: "ocr", code: "SOURCE_METADATA_REQUIRED", fields: [], evidence: { ocr_pages: [1] } }] }] }));
    }));
    render(<KnowledgeIntake onResolved={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Xem OCR chưa xác minh trang 1" }));
    fireEvent.click(await screen.findByText("Vị trí chữ OCR và ngữ cảnh: 21 phần"));
    expect(screen.getByText("First occurrence")).toBeInTheDocument();
    expect(screen.getByText("Vùng ảnh: 1, 2, 30, 20 pixel.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Phần chữ OCR tiếp theo" }));
    await screen.findByText("Last occurrence");
    expect(paths.some(path => path.endsWith("/pages/1/ocr?offset=20&limit=20"))).toBe(true);
    expect(screen.queryByText("First occurrence")).toBeNull();
    expect(screen.getByText(/Điểm đọc chữ không xác nhận số liệu/)).toBeInTheDocument();
  });
});
