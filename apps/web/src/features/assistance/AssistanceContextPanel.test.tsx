import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { AssistanceContextPanel } from "./AssistanceContextPanel";

const id = "019a0000-0000-7000-8000-000000000001";
const value = { schema_version: "unified-assistance.v1", status: "observed", action_authority: "none",
  resource: { id, version: 3, view: "student", status: "SUBMITTED", workflow: "GRADE_APPEAL" },
  guidance: "Nguồn mô phỏng đã đối chiếu", limitations: ["Không xác nhận thay người dùng"],
  evidence: [{ source_id: "source", version_id: "v1", locator: "fixture / item 1", sha256: "a".repeat(64), classification: "synthetic" }] };
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("sends only typed references and renders source provenance for both roles", async () => {
  const fetch = vi.fn(async (_url: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({ context: { ...value, resource: { ...value.resource, view: "staff" } } }), { status: 200 }));
  vi.stubGlobal("fetch", fetch);
  render(<AssistanceContextPanel id={id} version={3} />);
  fireEvent.click(screen.getByRole("button", { name: "Đối chiếu hồ sơ và nguồn" }));
  await screen.findByText("Nguồn mô phỏng đã đối chiếu");
  const request = JSON.parse(fetch.mock.calls[0][1]!.body as string);
  expect(request).toEqual({ surface: "service", resource: { kind: "service_request", id, expected_version: 3 } });
  expect(screen.getByText(/fixture \/ item 1/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /gửi|phê duyệt/i })).toBeNull();
});

describe.each([409, 503, 401])("failure %i", status => {
  it("reports failure without fabricated guidance or saved success", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status })));
    render(<AssistanceContextPanel id={id} version={3} />);
    fireEvent.click(screen.getByRole("button", { name: "Đối chiếu hồ sơ và nguồn" }));
    await screen.findByRole("alert");
    expect(screen.queryByText("Nguồn mô phỏng đã đối chiếu")).toBeNull();
  });
});

it("rejects a response bound to another resource or version", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ context: { ...value, resource: { ...value.resource, version: 2 } } }), { status: 200 })));
  render(<AssistanceContextPanel id={id} version={3} />);
  fireEvent.click(screen.getByRole("button", { name: "Đối chiếu hồ sơ và nguồn" }));
  await screen.findByRole("alert");
  expect(screen.queryByText("Nguồn mô phỏng đã đối chiếu")).toBeNull();
});

it("suppresses a late response after selecting another case", async () => {
  let resolve!: (r: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(r => { resolve = r; })));
  const view = render(<AssistanceContextPanel id={id} version={3} />);
  fireEvent.click(screen.getByRole("button", { name: "Đối chiếu hồ sơ và nguồn" }));
  view.rerender(<AssistanceContextPanel id="019a0000-0000-7000-8000-000000000002" version={1} />);
  resolve(new Response(JSON.stringify({ context: value }), { status: 200 }));
  await Promise.resolve();
  expect(screen.queryByText("Nguồn mô phỏng đã đối chiếu")).toBeNull();
  expect(screen.getByRole("button", { name: "Đối chiếu hồ sơ và nguồn" })).toBeEnabled();
});
