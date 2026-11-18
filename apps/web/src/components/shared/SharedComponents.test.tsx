import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { StatusBadge, PriorityBadge } from "./StatusBadge";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { LoadingState } from "./LoadingState";
import { ConfirmDialog } from "./ConfirmDialog";

describe("Shared Components Suite (Wave 2: W2-1 through W2-8)", () => {
  it("StatusBadge maps statuses to accessible Vietnamese labels and colored indicators", () => {
    const { rerender } = render(<StatusBadge status="open" />);
    expect(screen.getByText("Mới tiếp nhận")).toBeDefined();

    rerender(<StatusBadge status="pending_officer" />);
    expect(screen.getByText("Chờ xử lý")).toBeDefined();

    rerender(<StatusBadge status="resolved" />);
    expect(screen.getByText("Hoàn tất")).toBeDefined();

    rerender(<StatusBadge status="in_review" />);
    expect(screen.getByText("Đang rà soát")).toBeDefined();
  });

  it("PriorityBadge renders normal and high priority badges correctly", () => {
    const { rerender } = render(<PriorityBadge priority="normal" />);
    expect(screen.getByText("Bình thường")).toBeDefined();

    rerender(<PriorityBadge priority="high" />);
    expect(screen.getByText("Khẩn cấp")).toBeDefined();
  });

  it("EmptyState renders icon, title, description, and optional action", () => {
    const onActionMock = vi.fn();
    render(
      <EmptyState
        title="Không có hồ sơ nào"
        description="Bạn chưa tạo hồ sơ yêu cầu nào gần đây."
        action={<button onClick={onActionMock}>Tạo yêu cầu mới</button>}
      />
    );

    expect(screen.getByText("Không có hồ sơ nào")).toBeDefined();
    expect(screen.getByText(/Bạn chưa tạo hồ sơ/i)).toBeDefined();
    const actionBtn = screen.getByRole("button", { name: "Tạo yêu cầu mới" });
    fireEvent.click(actionBtn);
    expect(onActionMock).toHaveBeenCalledTimes(1);
  });

  it("ErrorState renders error message and retry action", () => {
    const onRetryMock = vi.fn();
    render(
      <ErrorState
        title="Lỗi tải dữ liệu"
        description="Không thể kết nối đến máy chủ"
        onRetry={onRetryMock}
      />
    );

    expect(screen.getByText("Lỗi tải dữ liệu")).toBeDefined();
    expect(screen.getByText("Không thể kết nối đến máy chủ")).toBeDefined();
    const retryBtn = screen.getByRole("button", { name: /Thử lại/i });
    fireEvent.click(retryBtn);
    expect(onRetryMock).toHaveBeenCalledTimes(1);
  });

  it("LoadingState renders title and description with spinner", () => {
    render(<LoadingState title="Đang nạp dữ liệu..." description="Vui lòng chờ giây lát" />);
    expect(screen.getByText("Đang nạp dữ liệu...")).toBeDefined();
    expect(screen.getByText("Vui lòng chờ giây lát")).toBeDefined();
  });

  it("ConfirmDialog triggers onConfirm and onCancel correctly", () => {
    const onConfirmMock = vi.fn();
    const onCancelMock = vi.fn();

    render(
      <ConfirmDialog
        isOpen={true}
        onCancel={onCancelMock}
        onConfirm={onConfirmMock}
        title="Xác nhận gửi yêu cầu"
        description="Bạn có chắc chắn muốn gửi yêu cầu này không?"
        confirmLabel="Đồng ý gửi"
      />
    );

    expect(screen.getByText("Xác nhận gửi yêu cầu")).toBeDefined();
    expect(screen.getByText(/Bạn có chắc chắn muốn gửi/i)).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Đồng ý gửi" }));
    expect(onConfirmMock).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Hủy" }));
    expect(onCancelMock).toHaveBeenCalledTimes(1);
  });
});
