import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { CitationDrawer, type CitationItem } from "./CitationDrawer";
import { ClaimEvidence } from "./ClaimEvidence";
import * as reviewStates from "../../lib/use-source-review-states";

describe("CitationDrawer Component (TASK-WEB-CITE-002)", () => {
  afterEach(() => {
    cleanup();
  });

  const mockCitations: CitationItem[] = [
    {
      id: "cite-1",
      title: "Quy định Đào tạo Đại học Chính quy HUCE 2025",
      documentRef: "QĐ-2025/ĐH-HUCE",
      quote: "Sinh viên hoàn thành học phí trước tuần 5 của học kỳ.",
      authority: "Phòng Quản lý Đào tạo HUCE",
      locator: "Điều 12, Khoản 3, Trang 14",
      effectiveDate: "01/09/2024",
      validityStatus: "active",
      confidence: 0.95, // Must NOT be rendered as percentage!
    },
  ];

  it("renders verifiable citation details without numeric confidence percentage", () => {
    const handleClose = vi.fn();
    render(
      <CitationDrawer
        isOpen={true}
        citations={mockCitations}
        onClose={handleClose}
      />
    );

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeDefined();
    expect(screen.getByText("Nguồn trích dẫn & Bằng chứng")).toBeDefined();
    expect(screen.getByText("Quy định Đào tạo Đại học Chính quy HUCE 2025")).toBeDefined();
    expect(screen.getByText(/QĐ-2025\/ĐH-HUCE/i)).toBeDefined();

    // Verifiable metadata fields
    expect(screen.getByText(/Phòng Quản lý Đào tạo HUCE/i)).toBeDefined();
    expect(screen.getByText(/Điều 12, Khoản 3, Trang 14/i)).toBeDefined();
    expect(screen.getByText(/Văn bản đang hiệu lực/i)).toBeDefined();

    // AC-01: Must NOT display raw numeric confidence percentage
    expect(screen.queryByText(/Độ tin cậy: 95%/i)).toBeNull();
    expect(screen.queryByText(/95%/i)).toBeNull();

    const closeBtn = screen.getByRole("button", { name: "Đóng" });
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("renders stale and conflicting evidence states clearly", () => {
    const multiCitations: CitationItem[] = [
      {
        id: "cite-stale",
        title: "Quy định Học vụ Cũ 2020",
        documentRef: "QĐ-2020/ĐH",
        quote: "Nội dung quy định học phần thay thế cũ.",
        validityStatus: "stale",
      },
      {
        id: "cite-conflict",
        title: "Thông báo hướng dẫn tạm thời",
        documentRef: "TB-2024/ĐH",
        quote: "Hướng dẫn thực hiện môn học mới.",
        validityStatus: "conflicting",
      },
    ];

    render(
      <CitationDrawer
        isOpen={true}
        citations={multiCitations}
        onClose={() => {}}
      />
    );

    expect(screen.getByText(/Văn bản cần đối chiếu/i)).toBeDefined();
    expect(screen.getByText(/Có nội dung mâu thuẫn/i)).toBeDefined();
  });

  it("masks unauthorized evidence correctly", () => {
    const unauthCitations: CitationItem[] = [
      {
        id: "cite-unauth",
        title: "Secret Document",
        documentRef: "SEC-123",
        quote: "Secret quote.",
        isAuthorized: false,
      }
    ];

    render(
      <CitationDrawer
        isOpen={true}
        citations={unauthCitations}
        onClose={() => {}}
      />
    );

    expect(screen.getByText(/Tài liệu hạn chế truy cập/i)).toBeDefined();
    expect(screen.queryByText(/Secret Document/i)).toBeNull();
    expect(screen.queryByText(/Secret quote/i)).toBeNull();
    expect(screen.queryByText(/SEC-123/i)).toBeNull();
  });

  it("returns focus to trigger element when closed", () => {
    const button = document.createElement("button");
    button.textContent = "Mở nguồn";
    document.body.appendChild(button);
    button.focus();

    const handleClose = vi.fn();
    const { rerender } = render(
      <CitationDrawer
        isOpen={true}
        citations={mockCitations}
        onClose={handleClose}
      />
    );

    const closeBtn = screen.getByRole("button", { name: "Đóng" });
    fireEvent.click(closeBtn);

    rerender(
      <CitationDrawer
        isOpen={false}
        citations={mockCitations}
        onClose={handleClose}
      />
    );

    expect(document.activeElement).toBe(button);
    document.body.removeChild(button);
  });
});

describe("ClaimEvidence Component (TASK-WEB-CITE-003)", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders supported claim with citation indices", () => {
    const handleClick = vi.fn();
    render(
      <ClaimEvidence 
        text="Sinh viên phải đóng học phí đúng hạn." 
        citationIndices={[1, 2]} 
        onCitationClick={handleClick}
      />
    );

    expect(screen.getByText(/Sinh viên phải đóng học phí đúng hạn/i)).toBeDefined();
    
    const btn1 = screen.getByRole("button", { name: "Xem nguồn trích dẫn 1" });
    const btn2 = screen.getByRole("button", { name: "Xem nguồn trích dẫn 2" });
    expect(btn1).toBeDefined();
    expect(btn2).toBeDefined();
    
    fireEvent.click(btn1);
    expect(handleClick).toHaveBeenCalledWith(1);
  });

  it("renders unsupported claim distinctly", () => {
    render(
      <ClaimEvidence 
        text="Thông tin chưa được xác thực." 
        isUnsupported={true} 
      />
    );

    const span = screen.getByTestId("unsupported-claim");
    expect(span.getAttribute("title")).toBe("Nội dung chưa được kiểm chứng");
    expect(screen.getByText(/Thông tin chưa được xác thực/i)).toBeDefined();
  });
});

describe("CitationDrawer review label", () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });
  const item = (id: string, sourceId?: string): CitationItem => ({ id, sourceId, title: `Nguồn ${id}`, documentRef: "v1", quote: "Nội dung trích", validityStatus: "active" });

  it("labels a source that is overdue for review and leaves the others alone", () => {
    vi.spyOn(reviewStates, "useSourceReviewStates").mockReturnValue({ s1: "OVERDUE", s2: "OK" });
    render(<CitationDrawer isOpen citations={[item("c1", "s1"), item("c2", "s2"), item("c3")]} onClose={() => {}} />);
    expect(screen.getAllByText("Nguồn quá hạn rà soát — nên đối chiếu văn bản gốc")).toHaveLength(1);
    expect(screen.getByText("Nguồn c1").closest("article")?.textContent).toContain("quá hạn rà soát");
    expect(screen.getByText("Nguồn c2").closest("article")?.textContent).not.toContain("quá hạn rà soát");
  });

  it("looks the states up only for sources with an id, and only while the drawer is open", () => {
    const spy = vi.spyOn(reviewStates, "useSourceReviewStates").mockReturnValue({});
    const { rerender } = render(<CitationDrawer isOpen citations={[item("c1", "s1"), item("c3")]} onClose={() => {}} />);
    expect(spy).toHaveBeenLastCalledWith(["s1"], true);
    rerender(<CitationDrawer isOpen={false} citations={[item("c1", "s1")]} onClose={() => {}} />);
    expect(spy).toHaveBeenLastCalledWith(["s1"], false);
  });
});
