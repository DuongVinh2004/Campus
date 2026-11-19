import React from "react";
import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  LearningOcrAnchor, LearningOcrJob, LearningOcrRelease, LearningOcrReviewRelease,
} from "../../lib/data/api/learning-gateway";
import { AccessibleText, OcrReleasePreview } from "./AccessibleText";
import { parseOcrPages } from "./AccessibleTextReview";

const actorId = "actor-test";
const versionId = "version-test";
const releaseId = "published-test";
const draftId = "draft-test";
const jobId = "job-test";
const textPath = `/v1/learning/versions/${versionId}/accessible-text`;
const jobsPath = `/v1/learning/versions/${versionId}/ocr-jobs`;
const draftPath = `/v1/learning/ocr-releases/${draftId}`;
const anchor: LearningOcrAnchor = { x: 0.14, y: 0.23, width: 0.44, height: 0.15 };
const publishedRelease: LearningOcrRelease = {
  id: releaseId, version_id: versionId, revision: 4, state: "PUBLISHED",
  page_count: 4, available_pages: [2, 4], missing_page_count: 2,
};
const draft: LearningOcrReviewRelease = {
  ...publishedRelease, id: draftId, revision: 1, state: "DRAFT", available_pages: [], missing_page_count: 4,
  current_release_id: releaseId, requested_pages: [2, 4], reviewed_pages: [],
};
const queued: LearningOcrJob = {
  id: jobId, release_id: draftId, version_id: versionId, revision: 1, state: "QUEUED",
  pages: [2, 4], requested_pages: 2, completed_pages: 0, errors: {},
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function setup(extra: Partial<React.ComponentProps<typeof AccessibleText>> = {}) {
  const onSource = vi.fn();
  const confirmWrite = vi.fn().mockResolvedValue({});
  render(<AccessibleText actorId={actorId} versionId={versionId} pageCount={4} sourcePage={1}
    canRead canManage={false} published onSource={onSource} confirmWrite={confirmWrite} {...extra}>
    <div data-testid="original-pdf">Ảnh PDF phiên bản gốc</div>
  </AccessibleText>);
  return { onSource, confirmWrite };
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("accessible PDF text", () => {
  it("reads reviewed semantic blocks, labels missing pages, and searches Vietnamese by exact source", async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), "https://learning.test");
      expect(new Headers(init?.headers).get("X-Campus-Reader-Actor")).toBe(actorId);
      if (url.pathname === textPath) return json({ release: publishedRelease, version_id: versionId });
      if (url.pathname === `${textPath}/pages/2`) return json({
        release_id: releaseId, version_id: versionId, page_no: 2, blocks: [
          { id: "heading", type: "HEADING", level: 3, text: "Đo điện áp", anchor },
          { id: "list", type: "LIST", ordered: true, items: ["Đặt que đo"], anchor },
          { id: "table", type: "TABLE", headers: ["Đại lượng", "Giá trị"], rows: [["Điện áp", "5 V"]], anchor },
          { id: "literal", type: "PARAGRAPH", text: "<script>chữ hiển thị</script>", anchor },
          { id: "placeholder", type: "PLACEHOLDER", text: "Mở ảnh gốc để đối chiếu.", anchor },
        ],
      });
      if (url.pathname === `${textPath}/search`) {
        expect(url.searchParams.get("q")).toBe("điện áp");
        return json({ release_id: releaseId, hits: [{ page_no: 4, block_id: "match" }], limit_reached: false });
      }
      if (url.pathname === `${textPath}/pages/4`) return json({
        release_id: releaseId, version_id: versionId, page_no: 4,
        blocks: [{ id: "match", type: "FORMULA", text: "Điện áp bằng tích dòng điện và điện trở.", anchor }],
      });
      throw new Error(`Unexpected request ${url.pathname}`);
    });
    vi.stubGlobal("fetch", fetcher);
    const { onSource } = setup();
    const original = screen.getByTestId("original-pdf");
    fireEvent.click(await screen.findByRole("button", { name: "Bản chữ hỗ trợ" }));
    expect(screen.getByText("Trang 1 chưa có bản chữ đã duyệt.")).toBeVisible();
    expect(screen.getByText(/2\/4 trang đã công bố/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Quản lý bản chữ" })).toBeNull();
    fireEvent.change(screen.getByLabelText("Trang bản chữ"), { target: { value: "2" } });
    expect(await screen.findByRole("heading", { name: "Đo điện áp", level: 3 })).toBeVisible();
    expect(screen.getByRole("listitem")).toHaveTextContent("Đặt que đo");
    expect(screen.getByRole("columnheader", { name: "Giá trị" })).toHaveAttribute("scope", "col");
    expect(screen.getByRole("cell", { name: "5 V" })).toBeVisible();
    expect(screen.getByText("<script>chữ hiển thị</script>")).toBeVisible();
    expect(screen.getByText("Mở ảnh gốc để đối chiếu.")).toBeVisible();
    expect(screen.getByTestId("original-pdf")).toBe(original);

    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "điện áp" } });
    fireEvent.click(screen.getByRole("button", { name: "Tìm bản chữ" }));
    fireEvent.click(await screen.findByRole("button", { name: "Kết quả 1 · Trang 4" }));
    const source = await screen.findByRole("button", { name: "Mở ảnh gốc trang 4 · Khối 1" });
    await waitFor(() => expect(source.parentElement).toHaveFocus());
    expect(onSource).toHaveBeenLastCalledWith(4, undefined, false);
    fireEvent.click(source);
    expect(onSource).toHaveBeenLastCalledWith(4, anchor, true);
    expect(screen.getByTestId("original-pdf")).toBe(original);
  });

  it("drops rendered text when the live source grant is revoked", async () => {
    let revoked = false;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const { pathname } = new URL(String(input), "https://learning.test");
      if (revoked) return json({ error: { code: "NOT_FOUND", message: "Không tìm thấy" } }, 404);
      if (pathname === textPath) return json({ release: publishedRelease, version_id: versionId });
      if (pathname === `${textPath}/pages/2`) return json({
        release_id: releaseId, version_id: versionId, page_no: 2, blocks: [{ id: "private", type: "PARAGRAPH", text: "Chữ đã duyệt", anchor }],
      });
      throw new Error(`Unexpected request ${pathname}`);
    }));
    setup({ sourcePage: 2 });
    fireEvent.click(await screen.findByRole("button", { name: "Bản chữ hỗ trợ" }));
    expect(await screen.findByText("Chữ đã duyệt")).toBeVisible();
    revoked = true;
    act(() => window.dispatchEvent(new Event("focus")));
    await waitFor(() => expect(screen.queryByText("Chữ đã duyệt")).toBeNull());
    expect(screen.queryByRole("button", { name: "Bản chữ hỗ trợ" })).toBeNull();
    expect(screen.getByTestId("original-pdf")).toBeVisible();
  });
});

describe("instructor OCR review", () => {
  it("loads quota, creates and resumes a job with scoped pages and revision", async () => {
    const requests: { path: string; method: string; payload: unknown; key: string | null }[] = [];
    let job: LearningOcrJob | undefined;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const { pathname } = new URL(String(input), "https://learning.test");
      const headers = new Headers(init?.headers);
      expect(headers.get("X-Campus-Reader-Actor")).toBe(actorId);
      if (pathname === jobsPath && init?.method === "POST") {
        requests.push({ path: pathname, method: init.method, payload: JSON.parse(String(init.body)), key: headers.get("Idempotency-Key") });
        job = { ...queued, revision: 2, state: "FAILED", errors: { "4": { code: "TIMEOUT", permanent: false } } };
        return json(job);
      }
      if (pathname === jobsPath) return json({
        jobs: job ? [job] : [], releases: job ? [draft] : [], daily_pages_remaining: 12, max_pages_per_job: 3, storage_available_bytes: 5242880,
      });
      if (pathname === draftPath) return json(draft);
      if (pathname === `/v1/learning/ocr-jobs/${jobId}` && init?.method === "PATCH") {
        requests.push({ path: pathname, method: init.method, payload: JSON.parse(String(init.body)), key: headers.get("Idempotency-Key") });
        job = { ...queued, revision: 3 };
        return json(job);
      }
      throw new Error(`Unexpected request ${pathname}`);
    }));
    setup({ canRead: false, canManage: true });
    fireEvent.click(screen.getByRole("button", { name: "Quản lý bản chữ" }));
    expect(await screen.findByText(/Còn 12 trang theo ngày.*5 MiB/)).toBeVisible();
    const range = screen.getByLabelText(/Trang cần tạo bản chữ/);
    fireEvent.change(range, { target: { value: "1–4" } });
    fireEvent.click(screen.getByRole("button", { name: "Yêu cầu OCR" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Chọn tối đa 3 trang mỗi yêu cầu.");
    expect(requests).toHaveLength(0);
    fireEvent.change(range, { target: { value: "4, 2, 2" } });
    fireEvent.click(screen.getByRole("button", { name: "Yêu cầu OCR" }));
    fireEvent.click(await screen.findByRole("button", { name: "Thử lại các trang lỗi" }));
    expect(await screen.findByText("Đang xếp hàng")).toBeVisible();
    expect(requests).toEqual([
      { path: jobsPath, method: "POST", payload: { pages: [2, 4] }, key: expect.any(String) },
      { path: `/v1/learning/ocr-jobs/${jobId}`, method: "PATCH", payload: { operation: "RESUME", revision: 2 }, key: expect.any(String) },
    ]);
  });

  it("verifies each risky structured block before saving and previews a reviewed subset", async () => {
    let reviewed: unknown;
    let release = draft;
    const candidate = {
      sha256: "candidate-fingerprint", blocks: [
        { id: "table", order: 1, text: "Ảnh OCR chưa đối chiếu", anchor, confidence: 50, provenance: "OCR", review_reasons: ["POSSIBLE_TABLE"] },
        { id: "formula", order: 2, text: "U = R × ?", anchor, confidence: 70, provenance: "OCR", review_reasons: ["POSSIBLE_FORMULA"] },
      ],
    };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), "https://learning.test");
      if (url.pathname === jobsPath) return json({
        jobs: [queued], releases: [release], daily_pages_remaining: 12, max_pages_per_job: 3, storage_available_bytes: 5242880,
      });
      if (url.pathname === draftPath && init?.method === "PATCH") {
        expect(new Headers(init.headers).get("Idempotency-Key")).toBeTruthy();
        reviewed = JSON.parse(String(init.body));
        release = { ...draft, revision: 2, reviewed_pages: [2, 4] };
        return json(release);
      }
      if (url.pathname === draftPath && url.searchParams.get("page_no") === "2") return json({ ...release, candidate });
      throw new Error(`Unexpected request ${url.pathname}`);
    }));
    const { onSource, confirmWrite } = setup({ canRead: false, canManage: true, sourcePage: 2 });
    fireEvent.click(screen.getByRole("button", { name: "Quản lý bản chữ" }));
    fireEvent.change(await screen.findByLabelText("Bản chữ cần xem"), { target: { value: draftId } });
    const table = within(await screen.findByRole("group", { name: "Khối 1" }));
    const formula = within(screen.getByRole("group", { name: "Khối 2" }));
    expect(table.getByLabelText("Loại khối")).toHaveValue("PLACEHOLDER");
    expect(formula.getByLabelText("Loại khối")).toHaveValue("PLACEHOLDER");
    fireEvent.click(table.getByRole("button", { name: "Đối chiếu khối 1 trên ảnh" }));
    expect(onSource).toHaveBeenLastCalledWith(2, anchor, true);
    fireEvent.change(table.getByLabelText("Loại khối"), { target: { value: "TABLE" } });
    fireEvent.change(table.getByLabelText(/Tiêu đề cột/), { target: { value: "Đại lượng | Giá trị" } });
    fireEvent.change(table.getByLabelText(/Giá trị bảng/), { target: { value: "Điện áp | 5 V" } });
    fireEvent.change(formula.getByLabelText("Loại khối"), { target: { value: "FORMULA" } });
    fireEvent.change(formula.getByLabelText("Chữ hoặc mô tả đã kiểm tra"), { target: { value: "Điện áp bằng điện trở nhân dòng điện." } });
    const checkedPage = screen.getByLabelText(/Tôi đã đối chiếu nội dung và thứ tự đọc/);
    fireEvent.click(checkedPage);
    fireEvent.click(screen.getByRole("button", { name: "Lưu duyệt trang 2" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/Hãy xác nhận đã đối chiếu các khối/);
    expect(reviewed).toBeUndefined();
    fireEvent.click(table.getByLabelText(/Tôi đã đối chiếu số liệu/));
    fireEvent.click(formula.getByLabelText(/Tôi đã đối chiếu số liệu/));
    expect(checkedPage).not.toBeChecked();
    fireEvent.click(checkedPage);
    fireEvent.click(screen.getByRole("button", { name: "Lưu duyệt trang 2" }));
    expect(await screen.findByText("Đã lưu duyệt trang.")).toBeVisible();
    expect(reviewed).toEqual({
      operation: "REVIEW_PAGE", revision: 1, page_no: 2, candidate_sha256: candidate.sha256, review_confirmed: true,
      blocks: [
        { id: "table", type: "TABLE", headers: ["Đại lượng", "Giá trị"], rows: [["Điện áp", "5 V"]], risk_verified: true },
        { id: "formula", type: "FORMULA", text: "Điện áp bằng điện trở nhân dòng điện.", risk_verified: true },
      ],
    });
    const publish = within(await screen.findByRole("group", { name: "Trang công bố cho sinh viên" }));
    fireEvent.click(publish.getByRole("checkbox", { name: "Trang 2" }));
    fireEvent.click(publish.getByRole("button", { name: "Xem trước công bố bản chữ" }));
    expect(confirmWrite).toHaveBeenCalledWith(`/ocr-releases/${draftId}`, {
      operation: "PUBLISH", revision: 2, pages: [2], expected_current_release_id: releaseId,
    }, "ocr-release-update", "Công bố bản chữ hỗ trợ", "PATCH");
    await screen.findByText("Đã công bố bản chữ hỗ trợ.");
  });

  it("shows the exact pages and partial coverage in the signed preview", () => {
    render(<OcrReleasePreview value={{ id: draftId, version_id: versionId, operation: "PUBLISH", revision: 2, pages: [2, 4], page_count: 4 }} />);
    expect(screen.getByText("Trang sẽ được công bố · 2, 4.")).toBeVisible();
    expect(screen.getByText("2/4 trang trong phiên bản PDF này.")).toBeVisible();
    expect(screen.getByText("Các trang còn lại đọc bằng ảnh PDF gốc.")).toBeVisible();
  });

  it("parses only bounded positive ranges", () => {
    expect(parseOcrPages("4, 1–3, 2", 8, 4)).toEqual([1, 2, 3, 4]);
    expect(() => parseOcrPages("3-2", 8, 4)).toThrow(/từ 1 đến 8/);
    expect(() => parseOcrPages("1, 0", 8, 4)).toThrow(/từ 1 đến 8/);
    expect(() => parseOcrPages("1, hai", 8, 4)).toThrow(/Nhập trang hoặc khoảng trang/);
  });
});
