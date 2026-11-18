import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import HomePage from "../features/home/HomeOverview";

describe("HomePage Component (TASK-WEB-HOME-002)", () => {
  it("renders the Stitch overview and supplied academic data without mock defaults", () => {
    render(<HomePage schedule={{ id: "fixture", courseName: "Học phần fixture", courseCode: "SYN01", room: "Phòng fixture", timeSlot: "09:00", lecturer: "Giảng viên fixture", syncTime: "Bản đọc fixture" }} tickets={[{ id: "fixture-ticket", code: "SYN-01", title: "Hồ sơ fixture", statusText: "Cần bổ sung", updatedAt: "10:00" }]} />);
    expect(screen.getByRole("heading", { level: 1, name: "Chào bạn, hôm nay cần hỗ trợ gì?" })).toBeDefined();
    expect(screen.getByRole("search", { name: /Tìm kiếm quy chế và thủ tục học vụ/i })).toBeDefined();
    expect(screen.getByRole("heading", { name: "Dịch vụ thiết yếu" })).toBeDefined();
    expect(screen.getByText(/Học phần fixture/)).toBeDefined();
    expect(screen.getByText(/Phòng fixture/)).toBeDefined();
    expect(screen.getByText("Hồ sơ fixture")).toBeDefined();
    expect(screen.getByText("Cần bổ sung")).toBeDefined();
    expect(screen.getByRole("link", { name: /Xem toàn bộ lịch/ }).getAttribute("href")).toBe("/schedule");
    expect(screen.getByRole("link", { name: /Xem tất cả yêu cầu/ }).getAttribute("href")).toBe("/tickets");
    expect(screen.getByRole("link", { name: /Xin giấy xác nhận/ }).getAttribute("href")).toBe("/tickets");
    expect(screen.getByRole("link", { name: /Tìm phòng học/ }).getAttribute("href")).toBe("/rooms");
  });

  it("does not fabricate academic records when data has not been supplied", () => {
    render(<HomePage />);
    expect(screen.queryByText(/Lập trình Web nâng cao/)).toBeNull();
    expect(screen.queryByText(/TK-2026-01/)).toBeNull();
    expect(screen.getByText("Lịch học chưa được tích hợp")).toBeDefined();
  });

  it("handles empty or partial schedule states gracefully", () => {
    render(<HomePage searchParams={{ empty_schedule: "true" }} />);
    expect(screen.getByText(/Chưa có lịch học mới/i)).toBeDefined();
  });

  it("handles empty tickets summary gracefully", () => {
    render(<HomePage searchParams={{ empty_tickets: "true" }} />);
    expect(screen.getByText(/Bạn chưa có hồ sơ nào/i)).toBeDefined();
  });
});

describe("HomePage Component (TASK-WEB-HOME-003: Live capability truth & safety)", () => {
  it("AC-TASK-WEB-HOME-003-01: renders anonymous / unauthenticated state without fabricating private student data", () => {
    render(<HomePage searchParams={{ auth: "anonymous" }} />);

    // When anonymous, private schedule and ticket records must NOT be fabricated
    expect(screen.queryByText(/Lập trình Web nâng cao/i)).toBeNull();
    expect(screen.queryByText(/Xin cấp lại thẻ sinh viên/i)).toBeNull();

    // Login action shown when unauthenticated
    expect(screen.getByRole("link", { name: /Đăng nhập để xem lịch/i }).getAttribute("href")).toBe("/login?redirect=/schedule");

    // Must clearly state that login is required to access personal schedule & tickets
    expect(screen.getByText(/Vui lòng đăng nhập để xem lịch học cá nhân/i)).toBeDefined();
    expect(screen.getByText(/Vui lòng đăng nhập để theo dõi hồ sơ một cửa/i)).toBeDefined();

    // Private actions should indicate requirement to authenticate
    const scheduleAction = screen.getByRole("link", { name: /Xem lịch học/i });
    expect(scheduleAction.getAttribute("href")).toContain("/login");
  });

  it("AC-TASK-WEB-HOME-003-02: marks unavailable actions as disabled and does not present them as usable", () => {
    render(
      <HomePage
        unavailableCapabilities={["rooms", "chat"]}
      />
    );

    // Room lookup should be disabled
    const roomAction = screen.getByRole("button", { name: /Tìm phòng học/i });
    expect(roomAction.getAttribute("aria-disabled")).toBe("true");
    expect(screen.getAllByText(/Tạm ngừng/i).length).toBeGreaterThan(0);

    // Chat search form should have input and button disabled
    const chatInput = screen.getByLabelText(/Hỏi Trợ lý AI về quy chế, tín chỉ, lịch thi/i) as HTMLInputElement;
    expect(chatInput.disabled).toBe(true);
    expect(chatInput.placeholder).toContain("Tạm ngừng phục vụ");

    const submitBtn = screen.getByRole("button", { name: /Tạm ngừng phục vụ/i }) as HTMLButtonElement;
    expect(submitBtn.disabled).toBe(true);
  });

  it("AC-TASK-WEB-HOME-003-03: renders degraded state explaining impact and safe next action without pretending success", () => {
    render(
      <HomePage
        systemStatus={{
          mode: "degraded",
          message: "Hệ thống tra cứu thời khóa biểu đang bị gián đoạn do bảo trì cơ sở dữ liệu.",
          affectedServices: ["Thời khóa biểu", "Tra cứu phòng"],
          impact: "Dữ liệu lịch học có thể bị trễ và không phản ánh thay đổi phòng học trong hôm nay.",
          safeNextAction: "Vui lòng đối chiếu với thông báo trực tiếp từ Khoa hoặc giảng viên bộ môn.",
        }}
      />
    );

    // Capability banner rendered with degraded state
    expect(screen.getByRole("region", { name: /Cảnh báo vận hành và chỉ số KPI/i })).toBeDefined();
    expect(screen.getByText(/Cảnh báo vận hành hệ thống \[!\] SUY GIẢM/i)).toBeDefined();
    expect(screen.getByText(/Ảnh hưởng thực tế:/i)).toBeDefined();
    expect(screen.getByText(/Dữ liệu lịch học có thể bị trễ/i)).toBeDefined();
    expect(screen.getByText(/Hành động an toàn khuyến nghị:/i)).toBeDefined();
    expect(screen.getByText(/Vui lòng đối chiếu với thông báo trực tiếp/i)).toBeDefined();
  });

  it("AC-TASK-WEB-HOME-003-99: handles loading and failure states with retry capability", () => {
    // Loading state
    const { unmount } = render(<HomePage status="loading" />);
    expect(screen.getByText(/Đang đồng bộ trạng thái học vụ/i)).toBeDefined();
    unmount();

    // Error / Outage state with onRetry
    let retryCalled = false;
    render(
      <HomePage
        status="error"
        errorMessage="Không thể kết nối máy chủ dữ liệu học vụ"
        onRetry={() => { retryCalled = true; }}
      />
    );

    expect(screen.getByText(/Không thể kết nối máy chủ dữ liệu học vụ/i)).toBeDefined();
    const retryBtn = screen.getByRole("button", { name: /Thử lại/i });
    retryBtn.click();
    expect(retryCalled).toBe(true);
  });
});

