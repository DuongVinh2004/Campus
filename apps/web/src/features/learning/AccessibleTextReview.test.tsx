import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { LearningOcrCandidateBlock, LearningOcrJob, LearningOcrReviewRelease } from "../../lib/data/api/learning-gateway";
import { AccessibleTextReview } from "./AccessibleTextReview";

const versionId = "version-test";
const releaseId = "draft-test";
const jobsPath = `/v1/learning/versions/${versionId}/ocr-jobs`;
const releasePath = `/v1/learning/ocr-releases/${releaseId}`;
const release: LearningOcrReviewRelease = {
  id: releaseId, version_id: versionId, revision: 1, state: "DRAFT",
  page_count: 4, available_pages: [], missing_page_count: 4,
  current_release_id: null, requested_pages: [1, 2, 3, 4], reviewed_pages: [2],
};
const job: LearningOcrJob = {
  id: "job-test", version_id: versionId, release_id: releaseId, revision: 3, state: "NEEDS_REVIEW",
  pages: release.requested_pages, requested_pages: 4, completed_pages: 3,
  errors: { "3": { code: "TIMEOUT", permanent: false } },
};
const riskyBlock: LearningOcrCandidateBlock = {
  id: "block", order: 1, text: "4,5 V", anchor: { x: 0.1, y: 0.2, width: 0.3, height: 0.1 },
  confidence: 67, provenance: "OCR",
  review_reasons: ["READING_ORDER_REVIEW", "OCR_TEXT_REVIEW", "POSSIBLE_TABLE", "MULTI_COLUMN_LAYOUT"],
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function jobs(draft: LearningOcrReviewRelease) {
  return json({ jobs: [job], releases: [draft], daily_pages_remaining: 12, max_pages_per_job: 10, storage_available_bytes: 0 });
}

async function openReview() {
  const onSource = vi.fn();
  const confirmWrite = vi.fn();
  render(<AccessibleTextReview actorId="lecturer-test" versionId={versionId} pageCount={4} sourcePage={1} enabled published
    onSource={onSource} onReleaseChange={vi.fn()} confirmWrite={confirmWrite} />);
  const select = await screen.findByLabelText("Bản chữ cần xem");
  fireEvent.change(select, { target: { value: releaseId } });
  await screen.findByRole("group", { name: "Khối 1" });
  return { onSource, confirmWrite };
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("asks for fresh block verification after a table edit and describes how to handle columns", async () => {
  const write = vi.fn();
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "https://learning.test");
    if (url.pathname === jobsPath) return jobs(release);
    if (url.pathname === releasePath && init?.method === "PATCH") {
      write(JSON.parse(String(init.body)));
      return json({ ...release, revision: 2 });
    }
    if (url.pathname === releasePath && url.searchParams.get("page_no") === "1") {
      return json({ ...release, candidate: { sha256: "candidate-one", blocks: [riskyBlock] } });
    }
    throw new Error(`Unexpected request ${url}`);
  });
  await openReview();
  expect(screen.getByText(/Đối chiếu chữ theo từng cột/)).toBeVisible();
  expect(screen.getByText(/Nếu chưa đối chiếu được đầy đủ một khối/)).toBeVisible();
  const block = within(screen.getByRole("group", { name: "Khối 1" }));
  expect(block.getByText("Cần kiểm tra thứ tự đọc")).toBeVisible();
  expect(block.getByText("Có thể có nhiều cột")).toBeVisible();
  const type = block.getByLabelText("Loại khối");
  expect(type).toHaveValue("PLACEHOLDER");
  fireEvent.change(type, { target: { value: "TABLE" } });
  fireEvent.change(block.getByLabelText(/Tiêu đề cột/), { target: { value: "Điện áp" } });
  const rows = block.getByLabelText(/Giá trị bảng/);
  fireEvent.change(rows, { target: { value: "4,5 V" } });
  const blockChecked = block.getByLabelText(/Tôi đã đối chiếu số liệu/);
  const pageChecked = screen.getByLabelText(/Tôi đã đối chiếu nội dung và thứ tự đọc/);
  fireEvent.click(blockChecked);
  fireEvent.click(pageChecked);
  fireEvent.change(rows, { target: { value: "−4,5 V" } });
  expect(blockChecked).not.toBeChecked();
  expect(pageChecked).not.toBeChecked();
  fireEvent.click(pageChecked);
  fireEvent.click(screen.getByRole("button", { name: "Lưu duyệt trang 1" }));
  expect(screen.getByRole("alert")).toHaveTextContent(/Hãy xác nhận đã đối chiếu các khối/);
  expect(write).not.toHaveBeenCalled();

  fireEvent.click(blockChecked);
  fireEvent.click(pageChecked);
  fireEvent.click(screen.getByRole("button", { name: "Lưu duyệt trang 1" }));
  expect(await screen.findByText("Đã lưu duyệt trang.")).toBeVisible();
  expect(write).toHaveBeenCalledWith(expect.objectContaining({
    revision: 1, candidate_sha256: "candidate-one", page_no: 1,
    blocks: [{ id: "block", type: "TABLE", headers: ["Điện áp"], rows: [["−4,5 V"]], risk_verified: true }],
  }));
});

it("advances and focuses the next unreviewed page only after the server confirms the save", async () => {
  let draft = release;
  let finishWrite: ((status: number) => void) | undefined;
  const patchBodies: unknown[] = [];
  const loadedPages: string[] = [];
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "https://learning.test");
    if (url.pathname === jobsPath) return jobs(draft);
    if (url.pathname === releasePath && init?.method === "PATCH") {
      expect(new Headers(init.headers).get("Idempotency-Key")).toBeTruthy();
      patchBodies.push(JSON.parse(String(init.body)));
      const status = await new Promise<number>(resolve => { finishWrite = resolve; });
      if (status === 409) {
        draft = { ...draft, revision: 2 };
        return json({ code: "REVISION_CONFLICT" }, status);
      }
      draft = { ...draft, revision: 3, reviewed_pages: [1, 2] };
      return json(draft);
    }
    const page = url.searchParams.get("page_no");
    if (url.pathname === releasePath && (page === "1" || page === "4")) {
      loadedPages.push(page);
      return json({ ...draft, candidate: { sha256: `candidate-${page}`, blocks: [riskyBlock] } });
    }
    throw new Error(`Unexpected request ${url}`);
  });
  const { onSource, confirmWrite } = await openReview();
  expect(screen.getByRole("option", { name: "Trang 2 · Đã duyệt" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "Trang 3 · Lỗi OCR" })).toBeInTheDocument();
  const advance = () => {
    fireEvent.click(screen.getByLabelText(/Tôi đã đối chiếu nội dung và thứ tự đọc/));
    const button = screen.getByRole("button", { name: "Lưu và đến trang 4" });
    button.focus();
    fireEvent.click(button);
  };
  expect(screen.getByRole("button", { name: "Lưu và đến trang 4" })).toBeDisabled();
  advance();
  expect(screen.getByLabelText("Bản chữ cần xem")).toBeDisabled();
  expect(screen.getByLabelText("Trang cần đối chiếu")).toHaveValue("1");
  expect(loadedPages).toEqual(["1"]);
  finishWrite?.(409);
  expect(await screen.findByRole("alert")).toHaveTextContent(/Dữ liệu đã đổi/);
  expect(onSource).toHaveBeenCalledTimes(1);
  expect(loadedPages).toEqual(["1"]);

  fireEvent.click(screen.getByRole("button", { name: "Tải lại quản lý bản chữ" }));
  await screen.findByRole("group", { name: "Khối 1" });
  advance();
  expect(patchBodies).toEqual([1, 2].map(revision => ({
    operation: "REVIEW_PAGE", revision, page_no: 1, candidate_sha256: "candidate-1", review_confirmed: true,
    blocks: [{ id: "block", type: "PLACEHOLDER" }],
  })));
  finishWrite?.(200);
  expect(await screen.findByText("Đã lưu duyệt trang.")).toBeVisible();
  const heading = screen.getByRole("heading", { name: "Duyệt trang 4" });
  await waitFor(() => expect(heading).toHaveFocus());
  expect(await screen.findByRole("group", { name: "Khối 1" })).toBeVisible();
  expect(screen.getByText("2/4 trang đã duyệt.")).toBeVisible();
  expect(screen.queryByRole("button", { name: /Lưu và đến trang/ })).not.toBeInTheDocument();
  expect(loadedPages).toEqual(["1", "1", "4"]);
  expect(onSource).toHaveBeenLastCalledWith(4, undefined, false);
  expect(confirmWrite).not.toHaveBeenCalled();
});

it("numbers text releases by creation order, not by where the server lists them", async () => {
  const newest: LearningOcrReviewRelease = { ...release, id: "b-newer-draft", revision: 1, state: "DRAFT", current_release_id: "a-older-published" };
  const oldest: LearningOcrReviewRelease = { ...release, id: "a-older-published", revision: 2, state: "PUBLISHED", available_pages: [2], current_release_id: "a-older-published" };
  vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
    const url = new URL(String(input), "https://learning.test");
    if (url.pathname === jobsPath) return json({ jobs: [job], releases: [oldest, newest], daily_pages_remaining: 12, max_pages_per_job: 10, storage_available_bytes: 0 });
    throw new Error(`Unexpected request ${url}`);
  });
  render(<AccessibleTextReview actorId="lecturer-test" versionId={versionId} pageCount={4} sourcePage={1} enabled published
    onSource={vi.fn()} onReleaseChange={vi.fn()} confirmWrite={vi.fn()} />);
  const select = await screen.findByLabelText("Bản chữ cần xem");
  expect(within(select).getByText(/Bản nháp · Bản 2 · Lần 1/)).toBeInTheDocument();
  expect(within(select).getByText(/Đã công bố · Bản 1 · Lần 2 · Hiện hành/)).toBeInTheDocument();
});
