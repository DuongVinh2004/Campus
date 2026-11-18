import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { WorkflowDefinitionPanel } from "./WorkflowDefinitionPanel";

const id = "019a0000-0000-7000-8000-000000000001";
const value = { schema_version: "unified-workflow.v1", resource: { id, kind: "service_request", version: 3, view: "student" },
  definition_version: "service-workflow-demo-v1", classification: "synthetic", action_authority: "none",
  binding_status: "bound", current_source_differs: true, readiness: "requires_officer_review",
  institutional_rules_verified: false, supplements: [],
  binding: { workflow_version: "service-workflow-demo-v1", template_version: "template-v1",
    as_of: "2026-10-14T01:35:39+00:00", sha256: "a".repeat(64),
    supporting_sources: [], source_capture_at: null,
    source: { version_id: "source-v1", locator: "Fixture locator", source_sha256: "c".repeat(64),
      rendition_sha256: "b".repeat(64), classification: "synthetic", effective_status: "demo_interval",
      effective_from: "2026-10-13T00:00:00+00:00", effective_until: null } },
  template: { version: "template-v1", title: "Kết quả mô phỏng" },
  mandatory_reviews: [{ id: "evidence_review", label: "Đối chiếu bằng chứng", required: true,
    reviewer: "SUPPORT_OFFICER", status: "required" }] };
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("sends only references and shows historical binding without review completion or action buttons", async () => {
  const fetch = vi.fn(async (_url: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify(value), { status: 200 }));
  vi.stubGlobal("fetch", fetch);
  render(<WorkflowDefinitionPanel id={id} version={3} />);
  fireEvent.click(screen.getByRole("button", { name: "Xem quy trình áp dụng" }));
  await screen.findByText(/Đã đối chiếu phiên bản áp dụng/);
  expect(JSON.parse(fetch.mock.calls[0][1]!.body as string)).toEqual({ resource: { kind: "service_request", id, expected_version: 3 } });
  expect(fetch.mock.calls[0][0]).toMatch(/workflows\/resolve$/);
  expect(fetch.mock.calls[0][1]!.cache).toBe("no-store");
  expect(screen.getByText(/Nguồn hiện tại khác nguồn/)).toBeInTheDocument();
  expect(screen.getByText(/Đối chiếu bằng chứng · Bắt buộc/)).toBeInTheDocument();
  expect(screen.queryByRole("checkbox")).toBeNull();
  expect(screen.queryByRole("button", { name: /gửi|phê duyệt|xác nhận/i })).toBeNull();
});

it("renders an unresolved source without a template or invented ready status", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ ...value,
    binding_status: "unresolved", readiness: "undetermined", binding: null, template: null }), { status: 200 })));
  render(<WorkflowDefinitionPanel id={id} version={3} />);
  fireEvent.click(screen.getByRole("button", { name: "Xem quy trình áp dụng" }));
  await screen.findByText("Chưa đủ nguồn để xác định mẫu hoặc kết luận");
  expect(screen.queryByText(/Mẫu mô phỏng:/)).toBeNull();
});

describe.each([409, 401, 503])("HTTP failure %i", status => {
  it("reports a failure and leaves no binding success", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status })));
    render(<WorkflowDefinitionPanel id={id} version={3} />);
    fireEvent.click(screen.getByRole("button", { name: "Xem quy trình áp dụng" }));
    await screen.findByRole("alert");
    expect(screen.queryByText(/Đã đối chiếu phiên bản áp dụng/)).toBeNull();
    expect(screen.getByRole("button", { name: "Xem quy trình áp dụng" })).toBeEnabled();
  });
});

describe.each([
  { action_authority: "execute" }, { resource: { ...value.resource, version: 2 } },
  { binding: { ...value.binding, template_version: "different-template" } },
  { mandatory_reviews: [{ ...value.mandatory_reviews[0], status: "completed" }] },
  { binding_status: "unresolved" }, { readiness: "ready" },
  { institutional_rules_verified: true }, { resource: { ...value.resource, kind: "certificate_request" } },
  { supplements: [{ sequence: 1, at: null, binding_status: "bound", source: null, reasons: [], source_changed_from_submission: false }] },
  { binding: { ...value.binding, source: { ...value.binding.source, classification: "public_snapshot", effective_status: "unknown" } } },
])("invalid package %j", changes => {
  it("rejects an injected authority, stale binding or completed review", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ ...value, ...changes }), { status: 200 })));
    render(<WorkflowDefinitionPanel id={id} version={3} />);
    fireEvent.click(screen.getByRole("button", { name: "Xem quy trình áp dụng" }));
    await screen.findByRole("alert");
    expect(screen.queryByText(/Đã đối chiếu phiên bản áp dụng/)).toBeNull();
  });
});

it("shows public certificate sources with unknown effectivity and sends the certificate reference", async () => {
  const source = { ...value.binding.source, classification: "public_snapshot", effective_status: "unknown", effective_from: null };
  const fetch = vi.fn(async (_url: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({ ...value,
    resource: { ...value.resource, kind: "certificate_request" },
    binding: { ...value.binding, source, supporting_sources: [{ ...source, locator: "Catalog fixture" }],
      source_capture_at: value.binding.as_of } }), { status: 200 }));
  vi.stubGlobal("fetch", fetch);
  render(<WorkflowDefinitionPanel id={id} version={3} kind="certificate_request" />);
  fireEvent.click(screen.getByRole("button", { name: "Xem quy trình áp dụng" }));
  await screen.findByText(/Đã đối chiếu phiên bản áp dụng/);
  expect(JSON.parse(fetch.mock.calls[0][1]!.body as string).resource.kind).toBe("certificate_request");
  expect(screen.getAllByText("Chưa xác minh ngày hiệu lực chính thức của nguồn.")).toHaveLength(2);
  expect(screen.getByText(/Bản chụp công khai: Catalog fixture/)).toBeInTheDocument();
});

it("preserves the initial binding but reports unknown legacy supplement provenance", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ ...value, readiness: "undetermined",
    supplements: [{ sequence: 1, at: null, binding_status: "unresolved", source: null,
      source_changed_from_submission: null, reasons: ["SUPPLEMENT_SOURCE_UNRECORDED"] }] }), { status: 200 })));
  render(<WorkflowDefinitionPanel id={id} version={3} />);
  fireEvent.click(screen.getByRole("button", { name: "Xem quy trình áp dụng" }));
  await screen.findByText(/Đã đối chiếu phiên bản áp dụng/);
  expect(screen.getByText(/Chưa ghi nhận thời điểm/)).toBeInTheDocument();
  expect(screen.getByText(/Chưa đủ lịch sử nguồn bổ sung/)).toBeInTheDocument();
  expect(screen.queryByText(/Còn kiểm tra của cán bộ/)).toBeNull();
});

it("discards a delayed package after the resource changes", async () => {
  let resolve!: (r: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(r => { resolve = r; })));
  const view = render(<WorkflowDefinitionPanel id={id} version={3} />);
  fireEvent.click(screen.getByRole("button", { name: "Xem quy trình áp dụng" }));
  view.rerender(<WorkflowDefinitionPanel id="019a0000-0000-7000-8000-000000000002" version={1} />);
  resolve(new Response(JSON.stringify(value), { status: 200 }));
  await Promise.resolve();
  expect(screen.queryByText(/Đã đối chiếu phiên bản áp dụng/)).toBeNull();
});
