import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { CitationDrawer } from "./CitationDrawer";
import { AppShell } from "../../components/AppShell";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.restoreAllMocks(); });
it("gives source titles their own row and wraps the full validity label and long identifiers", () => {
  vi.stubEnv("NEXT_PUBLIC_KNOWLEDGE_PLATFORM", "true");
  render(<CitationDrawer isOpen onClose={() => {}} citations={[{ id: "CIT-001",
    title: "Quy chế đào tạo HUCE — Quyết định 1486 ngày 06/11/2023",
    documentRef: "verified-effective-01a17057-0cbd-7504-a63c-b4c0ca345694", quote: "Đoạn nguồn nguyên văn." }]} />);
  const heading = screen.getByRole("heading", { level: 3 });
  expect(heading.parentElement?.style.flexDirection).toBe("column");
  expect(screen.getByText("Nguồn trong câu trả lời — mở để kiểm tra lại").style.whiteSpace).toBe("normal");
  expect(heading.closest("article")?.style.overflowWrap).toBe("anywhere");
});
it("places the mobile chat menu in document flow before the chat alert", () => {
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  render(<AppShell activeNav="chat"><p role="alert">Không thể khôi phục lịch sử đã xác nhận.</p></AppShell>);
  const menu = screen.getByRole("button", { name: "Mở điều hướng" });
  expect(menu.className).not.toMatch(/\b(absolute|fixed)\b/);
  expect(menu.getAttribute("aria-expanded")).toBe("false");
});
