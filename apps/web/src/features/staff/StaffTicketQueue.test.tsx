import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { StaffTicketQueue, type StaffQueueItem } from "./StaffTicketQueue";

describe("StaffTicketQueue Component (TASK-WEB-STAFF-002)", () => {
  afterEach(() => {
    cleanup();
  });

  const mockItems: StaffQueueItem[] = [
    {
      id: "queue-001",
      ticketCode: "TCK-2026-0101",
      studentName: "Trần Văn B",
      studentId: "1912345",
      title: "Đơn xin miễn giảm học phí",
      publicContent: "Em xin nộp bổ sung giấy xác nhận hộ nghèo năm 2026.",
      internalNotes: "Đã kiểm tra sơ bộ hồ sơ trên Cổng thông tin, cần xác minh dấu đỏ.",
      status: "unassigned",
      priority: "urgent",
      createdAt: "2026-09-22 09:00",
      age: "45 phút",
    },
    {
      id: "queue-002",
      ticketCode: "TCK-2026-0102",
      studentName: "Lê Thị C",
      studentId: "2012346",
      title: "Xin cấp lại thẻ sinh viên",
      publicContent: "Thẻ bị gãy chip từ tuần trước.",
      status: "assigned",
      assignedStaffId: "staff-huce-01",
      priority: "normal",
      createdAt: "2026-09-22 09:30",
      age: "15 phút",
    },
    {
      id: "queue-003",
      ticketCode: "TCK-2026-0103",
      studentName: "Phạm Hoàng D",
      studentId: "2112347",
      title: "Kỷ luật học vụ đặc biệt",
      publicContent: "Nội dung cần thẩm định thẩm quyền cấp phòng.",
      internalNotes: "Hồ sơ kỷ luật mật - chỉ cán bộ trưởng ca xử lý.",
      status: "unassigned",
      priority: "high",
      createdAt: "2026-09-22 08:00",
      age: "2 giờ",
      isRestricted: true,
    },
    {
      id: "queue-004",
      ticketCode: "TCK-2026-0104",
      studentName: "Vũ Minh E",
      studentId: "2212348",
      title: "Phúc khảo điểm thi môn Kết cấu thép",
      status: "unassigned",
      priority: "normal",
      createdAt: "2026-09-22 07:30",
      age: "3 giờ",
      hasConflict: true,
      conflictStaffId: "staff-huce-02",
    },
  ];

  it("renders queue items but blocks claim without a durable consumer", () => {
    const handleClaim = vi.fn();
    render(
      <StaffTicketQueue
        items={mockItems}
        currentStaffId="staff-huce-01"
        onClaimTicket={handleClaim}
      />
    );

    expect(screen.getByText("TCK-2026-0101")).toBeDefined();
    expect(screen.getByText("Đơn xin miễn giảm học phí")).toBeDefined();
    expect(screen.getByText("Trần Văn B (1912345)")).toBeDefined();

    // A callback alone does not authorize a business action.
    const claimBtn = screen.getByRole("button", { name: /Chưa có consumer - TCK-2026-0101/i });
    expect(claimBtn.hasAttribute("disabled")).toBe(true);
    fireEvent.click(claimBtn);

    expect(handleClaim).not.toHaveBeenCalled();
  });

  it("negative path: disables claim button for tickets already claimed by others", () => {
    render(
      <StaffTicketQueue
        items={mockItems}
        currentStaffId="staff-huce-99"
        onClaimTicket={() => {}}
      />
    );

    const alreadyClaimedBtn = screen.getByRole("button", { name: /Chưa có consumer - TCK-2026-0102/i });
    expect(alreadyClaimedBtn.hasAttribute("disabled")).toBe(true);
  });

  it("delegates claim to the connected consumer only after an explicit click", () => {
    const handleClaim = vi.fn();
    render(<StaffTicketQueue items={mockItems} currentStaffId="staff-huce-01" businessActionsAvailable onClaimTicket={handleClaim} />);
    expect(handleClaim).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Nhận xử lý TCK-2026-0101/i }));
    expect(handleClaim).toHaveBeenCalledTimes(1);
    expect(handleClaim).toHaveBeenCalledWith("queue-001");
  });

  it("prioritizes urgency and age with non-color textual indicators", () => {
    render(
      <StaffTicketQueue
        items={mockItems}
        currentStaffId="staff-huce-01"
      />
    );

    // Urgent badge with explicit non-color text
    const urgentBadge = screen.getByText(/\[!\] Khẩn cấp/i);
    expect(urgentBadge).toBeDefined();

    // Age / wait time displayed
    expect(screen.getByText(/45 phút/i)).toBeDefined();
    expect(screen.getByText(/15 phút/i)).toBeDefined();
  });

  it("distinguishes internal notes from public content semantically", () => {
    render(
      <StaffTicketQueue
        items={mockItems}
        currentStaffId="staff-huce-01"
      />
    );

    // Expand details for queue-001
    const expandBtn = screen.getByRole("button", { name: /Chi tiết TCK-2026-0101/i });
    fireEvent.click(expandBtn);

    // Both public content and staff-only internal notes exist but are labelled distinctly
    expect(screen.getByText(/Nội dung công khai/i)).toBeDefined();
    expect(screen.getByText(/Em xin nộp bổ sung giấy xác nhận hộ nghèo/i)).toBeDefined();

    expect(screen.getByText(/Ghi chú nội bộ/i)).toBeDefined();
    expect(screen.getByText(/Đã kiểm tra sơ bộ hồ sơ trên Cổng thông tin/i)).toBeDefined();
  });

  it("exposes claim conflicts explicitly with conflict notice and refresh action", () => {
    const handleRefresh = vi.fn();
    render(
      <StaffTicketQueue
        items={mockItems}
        currentStaffId="staff-huce-01"
        onRefresh={handleRefresh}
      />
    );

    // Check conflict warning on TCK-2026-0104
    expect(screen.getByText(/Xung đột tiếp nhận/i)).toBeDefined();
    expect(screen.getByText(/staff-huce-02/i)).toBeDefined();

    // Claim button is disabled due to conflict
    const conflictBtn = screen.getByRole("button", { name: /Chưa có consumer - TCK-2026-0104/i });
    expect(conflictBtn.hasAttribute("disabled")).toBe(true);

    // Refresh CTA exists
    const refreshBtn = screen.getByRole("button", { name: /Làm mới hàng đợi/i });
    fireEvent.click(refreshBtn);
    expect(handleRefresh).toHaveBeenCalled();
  });

  it("handles restricted access without leaking sensitive case details", () => {
    render(
      <StaffTicketQueue
        items={mockItems}
        currentStaffId="staff-huce-01"
      />
    );

    // queue-003 is restricted: sensitive title and student info should be masked or restricted badge shown
    expect(screen.getByText(/Hồ sơ hạn chế truy cập/i)).toBeDefined();
    expect(screen.queryByText(/Phạm Hoàng D/i)).toBeNull();

    // Claim button is disabled for restricted item
    const restrictedBtn = screen.getByRole("button", { name: /Chưa có consumer - TCK-2026-0103/i });
    expect(restrictedBtn.hasAttribute("disabled")).toBe(true);
  });

  it("filters queue by tabs and preserves accessible keyboard navigation", () => {
    render(
      <StaffTicketQueue
        items={mockItems}
        currentStaffId="staff-huce-01"
      />
    );

    const urgentFilterTab = screen.getByRole("tab", { name: /Khẩn cấp/i });
    fireEvent.click(urgentFilterTab);

    // In urgent filter, only TCK-2026-0101 should appear
    expect(screen.getByText("TCK-2026-0101")).toBeDefined();
    expect(screen.queryByText("TCK-2026-0102")).toBeNull();
  });

  it("denies access to unauthorized users without exposing staff actions (AC-TASK-WEB-STAFF-003-01)", () => {
    render(
      <StaffTicketQueue
        items={mockItems}
        currentStaffId="student-001"
        userRole="STUDENT"
      />
    );

    expect(screen.getByText(/Từ chối quyền truy cập/i)).toBeDefined();
    expect(screen.getByText(/Bạn không có thẩm quyền truy cập hàng đợi cán bộ/i)).toBeDefined();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByRole("button", { name: /Nhận xử lý/i })).toBeNull();
  });

  it("disables claim and shows version conflict when ticket is stale (AC-TASK-WEB-STAFF-003-02)", () => {
    const staleItems: StaffQueueItem[] = [
      {
        ...mockItems[0],
        isStale: true,
        version: 1,
      },
    ];

    render(
      <StaffTicketQueue
        items={staleItems}
        currentStaffId="staff-huce-01"
        userRole="STAFF"
      />
    );

    expect(screen.getAllByText(/Xung đột phiên bản/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Dữ liệu đã thay đổi trên máy chủ/i)).toBeDefined();

    const claimBtn = screen.getByRole("button", { name: /Chưa có consumer - TCK-2026-0101/i });
    expect(claimBtn.hasAttribute("disabled")).toBe(true);
  });

  it("renders result-unknown state visibly without false optimistic success (AC-TASK-WEB-STAFF-003-03)", () => {
    const handleReconcile = vi.fn();
    const unknownItems: StaffQueueItem[] = [
      {
        ...mockItems[0],
        actionOutcome: "unknown",
      },
    ];

    render(
      <StaffTicketQueue
        items={unknownItems}
        currentStaffId="staff-huce-01"
        userRole="STAFF"
        onReconcile={handleReconcile}
      />
    );

    expect(screen.getByText(/Chưa rõ kết quả/i)).toBeDefined();
    expect(screen.getByText(/Đang đối soát kết quả ghi nhận từ máy chủ/i)).toBeDefined();

    const reconcileBtn = screen.getByRole("button", { name: /Thử đối soát lại/i });
    fireEvent.click(reconcileBtn);
    expect(handleReconcile).toHaveBeenCalledWith("queue-001");
  });
});
