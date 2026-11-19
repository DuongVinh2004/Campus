import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { EditionWorkspace } from "./EditionWorkspace";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const axis = { kind: "UNKNOWN", values: [] };
const witness = { artifact_id: "original", artifact_sha256: "a".repeat(64), locator: { page_index: 0, char_start: 0, char_end: 12, extraction_sha256: "b".repeat(64) }, verbatim: "Exact source", text_sha256: "c".repeat(64) };
const identity = { tenant_id: "tenant", family_id: "source", issuer: "Synthetic publisher", document_number: null, issued_on: null,
  verification: "CANDIDATE", identity_basis: null, scope: { programmes: axis, cohorts: axis, academic_years: axis },
  effective: { from_day: null, until_day: null, end_kind: "UNKNOWN", timezone: "Asia/Bangkok", basis: null } };

function setup(canVerify = false) {
  const writes: Array<{ url: string; body: Record<string, unknown> }> = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { writes.push({ url, body: JSON.parse(String(init.body)) }); return new Response(JSON.stringify(url.endsWith("resolve-preview") ?
      { state: "NEEDS_INFORMATION", segments: [{ scope: { programmes: null }, selected: [], excluded: [], issues: [{ reason: "EFFECTIVE_START_UNKNOWN" }] }] } : { revision: 2 })); }
    return new Response(JSON.stringify({ state: "MAPPED", edition_id: "edition", source_id: "source", identity,
      expected_revision: url.includes("page_index=1") ? 99 : 1, can_verify: canVerify, total_pages: 2,
      page: { page_index: url.includes("page_index=1") ? 1 : 0, page: 1, text: "Exact source" }, page_witness: witness, related_editions: [], relations: [] }));
  }));
  return writes;
}

it("keeps unknown facts and the loaded revision when navigating source pages", async () => {
  const writes = setup(); render(<EditionWorkspace versionId="version" actorId="author" />);
  fireEvent.click(screen.getByRole("button", { name: "Đối chiếu định danh và quan hệ phiên bản" }));
  await screen.findByLabelText("Nhà ban hành");
  expect(screen.getByRole("option", { name: "Đã đối chiếu độc lập" })).toBeDisabled();
  expect(screen.getByLabelText("Ngày bắt đầu áp dụng")).toHaveValue("");
  fireEvent.change(screen.getByLabelText("Trang/khối chứa căn cứ"), { target: { value: "1" } });
  await waitFor(() => expect(screen.getByLabelText("Trang/khối chứa căn cứ")).toHaveValue("1"));
  fireEvent.click(screen.getByRole("button", { name: "Dùng trang này làm căn cứ định danh" }));
  fireEvent.change(screen.getByLabelText("Căn cứ quyết định"), { target: { value: "Synthetic source basis only, no effective date asserted." } });
  fireEvent.submit(screen.getByRole("button", { name: "Lưu quyết định phiên bản" }).closest("form")!);
  await screen.findByText(/Đã lưu quyết định có lịch sử/);
  expect(writes[0].body).toMatchObject({ expected_revision: 1, confirmed_source_basis: false,
    identity: { verification: "CANDIDATE", identity_basis: witness, effective: { from_day: null, end_kind: "UNKNOWN", basis: null }, scope: { cohorts: axis } } });
});

it("renders resolver reasons without claiming serving or silently inserting today's date", async () => {
  const writes = setup(true); render(<EditionWorkspace versionId="version" actorId="independent" />);
  fireEvent.click(screen.getByRole("button", { name: "Đối chiếu định danh và quan hệ phiên bản" }));
  await screen.findByLabelText("Nhà ban hành");
  expect(screen.getByLabelText("Ngày áp dụng cần hỏi")).toHaveValue("");
  fireEvent.change(screen.getByLabelText("Ngày áp dụng cần hỏi"), { target: { value: "2026-10-27" } });
  fireEvent.submit(screen.getByRole("button", { name: "Đối chiếu lựa chọn theo ngày và phạm vi" }).closest("form")!);
  await screen.findByText("Chưa rõ ngày bắt đầu");
  expect(writes[0].body).toEqual({ family_ids: ["source"], at_day: "2026-10-27", programmes: [], cohorts: [], academic_years: [] });
  expect(screen.getByText(/Kết quả xem trước chưa xác nhận phát hành/)).toBeInTheDocument();
});
