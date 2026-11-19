import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StudentPortal } from "./student/StudentPortal";
import { StaffShell } from "./staff/StaffShell";
import * as storeModule from "@/lib/store";
import * as studentWorkspaceModule from "@/lib/student-workspace";

vi.mock("next/navigation", () => ({
  usePathname: () => "/student",
}));

describe("Shell Components (Wave 1: W1-4 & W1-5)", () => {
  it("StudentPortal denies access when user is not logged in", () => {
    vi.spyOn(storeModule, "useStore").mockReturnValue({
      currentUser: null,
      isDataLoading: false,
    } as any);

    render(<StudentPortal><div>Secret Student Info</div></StudentPortal>);
    expect(screen.queryByText("Secret Student Info")).toBeNull();
    expect(screen.getByText(/Chưa có phiên đăng nhập/i)).toBeDefined();
  });

  it("StudentPortal renders content when user is student", () => {
    vi.spyOn(storeModule, "useStore").mockReturnValue({
      currentUser: { id: "SV001", name: "Nguyễn Văn An", role: "student" },
      isDataLoading: false,
    } as any);
    vi.spyOn(studentWorkspaceModule, "useStudentWorkspace").mockReturnValue({
      storageIssue: null,
    } as any);

    render(<StudentPortal><div>Hello Student Workspace</div></StudentPortal>);
    expect(screen.getByText("Hello Student Workspace")).toBeDefined();
    expect(screen.getByText(/Campus 24\/7/i)).toBeDefined();
  });

  it("StaffShell denies access when user is student instead of officer", () => {
    vi.spyOn(storeModule, "useStore").mockReturnValue({
      currentUser: { id: "SV001", name: "Nguyễn Văn An", role: "student" },
      isDataLoading: false,
    } as any);

    render(<StaffShell><div>Secret Staff Queue</div></StaffShell>);
    expect(screen.queryByText("Secret Staff Queue")).toBeNull();
    expect(screen.getByText(/Bạn không có quyền vào khu vực này/i)).toBeDefined();
  });

  it("StaffShell renders workspace when user is officer", () => {
    vi.spyOn(storeModule, "useStore").mockReturnValue({
      currentUser: { id: "OF001", name: "ThS. Trần Thu Hà", role: "officer", department: "Phòng Quản lý Đào tạo" },
      isDataLoading: false,
      dataConfig: { mode: "mock" },
    } as any);

    render(<StaffShell><div>Active Staff Workstation</div></StaffShell>);
    expect(screen.getByText("Active Staff Workstation")).toBeDefined();
    expect(screen.getByText("Hồ sơ dịch vụ")).toBeDefined();
    expect(screen.getAllByText("Rà soát học phần").length).toBeGreaterThanOrEqual(1);
  });
});
