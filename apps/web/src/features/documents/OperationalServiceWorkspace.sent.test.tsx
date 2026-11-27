import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

const submit = vi.hoisted(() => vi.fn());
vi.mock("@/components/AppShell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main> }));
vi.mock("@/lib/campus-ops-api", async importOriginal => ({ ...(await importOriginal<object>()), OPS_ENABLED: true, ticketsApi: { submit } }));
vi.mock("../tickets/SubmittedTickets", () => ({ SubmittedTickets: () => null }));
import { OperationalServiceWorkspace } from "./OperationalServiceWorkspace";

const form = { kind: "STUDENT_CERTIFICATE", reason: "Cần giấy xác nhận đang học", purpose: "Xin visa", course: "", recipient: "Đại sứ quán" };
const draft = { id: "sent-draft", version: 1, form, status: "DRAFT", sent_to_university: false, updated_at: "2026-11-01T00:00:00Z" };
beforeEach(() => {
  window.localStorage.clear();
  vi.spyOn(globalThis, "fetch").mockImplementation(async url => new Response(JSON.stringify(String(url).endsWith("/users/me")
    ? { display_name: "Sinh viên thử", roles: ["STUDENT"] } : { items: [draft] }), { headers: { "content-type": "application/json" } }));
  submit.mockResolvedValue({ id: "t1", code: "HS-2026-000999" });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState(null, "", "/"); });

it("marks a draft as sent after submission and removes its Submit button, also after a reload", async () => {
  const first = render(<OperationalServiceWorkspace history />);
  fireEvent.click(await screen.findByTestId("draft-submit-sent-draft"));
  fireEvent.click(screen.getByTestId("draft-submit-confirm-sent-draft"));
  expect(await screen.findByTestId("draft-sent-sent-draft")).toHaveTextContent("HS-2026-000999");
  expect(screen.queryByTestId("draft-submit-sent-draft")).toBeNull();
  first.unmount();
  render(<OperationalServiceWorkspace history />);
  await waitFor(() => expect(screen.getByTestId("draft-sent-sent-draft")).toHaveTextContent("HS-2026-000999"));
  expect(submit).toHaveBeenCalledTimes(1);
});
