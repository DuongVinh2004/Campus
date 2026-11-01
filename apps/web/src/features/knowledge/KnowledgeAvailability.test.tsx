import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { KnowledgeAvailability } from "./KnowledgeAvailability";

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("distinguishes unserved sources from pending historical versions", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ ready: true,
    message: "Nguồn HUCE đã phục vụ trong phạm vi ghi trên từng tài liệu.", serving_documents: 3,
    total_sources: 117, unserved_sources: 114, pending_versions: 122, historical_pending_versions: 3 }) })));
  render(<KnowledgeAvailability />);
  await waitFor(() => expect(screen.getByRole("status").textContent).toContain("114 nguồn chưa phục vụ"));
  expect(screen.getByRole("status").textContent).toContain("122 phiên bản chưa duyệt, gồm 3 bản lịch sử");
  expect(screen.getByRole("status").textContent).not.toContain("122 nguồn");
});

it("keeps availability unknown after a failed request", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false })));
  render(<KnowledgeAvailability />);
  await waitFor(() => expect(screen.getByRole("status").textContent).toContain("Chưa xác nhận"));
  expect(screen.getByRole("status").textContent).not.toContain("0 tài liệu đang phục vụ");
});

it("accounts for retained aliases without calling them unfinished documents", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ ready: true,
    message: "Nguồn đã phục vụ.", serving_documents: 114, total_sources: 117, unserved_sources: 3,
    equivalent_sources: 3, unresolved_sources: 0, pending_versions: 122, historical_pending_versions: 119,
    actionable_pending_versions: 0 }) })));
  render(<KnowledgeAvailability />);
  await waitFor(() => expect(screen.getByRole("status").textContent).toContain("3 nguồn trùng/liên kết được bao phủ"));
  expect(screen.getByRole("status").textContent).toContain("0 nguồn chưa được bao phủ");
  expect(screen.getByRole("status").textContent).toContain("Còn 0 phiên bản cần xử lý");
});
