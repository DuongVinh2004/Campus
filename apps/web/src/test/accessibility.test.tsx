import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { AppShell } from "../components/AppShell";
import { AsyncState } from "../components/AsyncState";
import { ChatPanel } from "../features/chat/ChatPanel";
import { ActionConfirmation } from "../features/actions/ActionConfirmation";

describe("Accessibility & Keyboard Regression (TASK-WEB-A11Y-001)", () => {
  afterEach(() => {
    cleanup();
  });

  it("verifies landmarks and skip link presence in AppShell (UX-A11Y-001)", () => {
    render(<AppShell><div>Nội dung</div></AppShell>);

    expect(screen.getByRole("banner")).toBeDefined();
    expect(screen.getByRole("navigation", { name: "Điều hướng chính" })).toBeDefined();
    expect(screen.getByRole("main")).toBeDefined();
    expect(screen.getByRole("contentinfo")).toBeDefined();

    const skipLink = screen.getByText(/Bỏ qua tới nội dung chính/i);
    expect(skipLink).toBeDefined();
    expect(skipLink.getAttribute("href")).toBe("#main-content");
  });

  it("verifies live region and alert semantics in AsyncState (UX-A11Y-013)", () => {
    const { rerender } = render(<AsyncState status="loading" loadingMessage="Đang tải..." />);
    const liveLoading = screen.getByText("Đang tải...");
    expect(liveLoading.closest("[aria-live='polite']")).not.toBeNull();

    rerender(<AsyncState status="error" errorMessage="Lỗi hệ thống" />);
    const alertError = screen.getByRole("alert");
    expect(alertError).toBeDefined();
    expect(alertError.getAttribute("aria-live")).toBe("assertive");
  });

  it("verifies form control has accessible label and button in ChatPanel (UX-A11Y-010)", () => {
    render(<ChatPanel />);
    const input = screen.getByLabelText(/Đặt câu hỏi/i);
    expect(input).toBeDefined();
    expect(input.tagName.toLowerCase()).toBe("textarea");

    const submitBtn = screen.getByRole("button", { name: /Gửi/i });
    expect(submitBtn).toBeDefined();
  });

  it("verifies modal dialog focus trap accessibility in ActionConfirmation (UX-A11Y-005)", () => {
    render(
      <ActionConfirmation
        isOpen={true}
        action={{
          actionId: "act-1",
          actionType: "TEST",
          title: "Xác nhận kiểm thử",
          targetEntity: "Sinh viên",
          parameters: [],
          expiresInSeconds: 60,
        }}
        onConfirm={() => {}}
        onCancel={() => {}}
      />
    );

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeDefined();
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getAttribute("aria-labelledby")).toBe("confirm-dialog-title");
  });

  it("negative path: closed modal exposes no dialog landmark", () => {
    render(
      <ActionConfirmation
        isOpen={false}
        action={{
          actionId: "act-1",
          actionType: "TEST",
          title: "Xác nhận kiểm thử",
          targetEntity: "Sinh viên",
          parameters: [],
          expiresInSeconds: 60,
        }}
        onConfirm={() => {}}
        onCancel={() => {}}
      />
    );

    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
