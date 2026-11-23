import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { LanguageProvider } from "../../lib/i18n";
import { GAP_CONSENT_VERSION, GapReport } from "./GapReport";

afterEach(() => { cleanup(); document.cookie = "lang=; path=/; max-age=0"; });

function setup(lang?: "en") {
  if (lang) document.cookie = `lang=${lang}; path=/`;
  const post = vi.fn();
  render(<LanguageProvider><GapReport question="Học phí nộp ở đâu?" client={{ post } as never} /></LanguageProvider>);
  return post;
}

describe("report missing information (P2)", () => {
  beforeEach(() => { document.cookie = "lang=; path=/; max-age=0"; });

  it("sends nothing until the student has read the terms and ticked the box", async () => {
    const post = setup();
    fireEvent.click(screen.getByRole("button", { name: "Báo thiếu thông tin" }));
    expect(await screen.findByText(/Lưu bao lâu: 90 ngày/)).toBeInTheDocument();
    const send = screen.getByRole("button", { name: "Gửi" });
    expect(send).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    expect(send).toBeEnabled();
    expect(post).not.toHaveBeenCalled();
  });

  it("sends the edited text with the consent version, shows the delete code and can delete", async () => {
    const post = setup();
    post.mockResolvedValueOnce({ delete_code: "ma-xoa-123", question: "Học phí kỳ này nộp ở đâu?", text_kept: true, expires_at: "2027-02-19T03:00:00Z" });
    post.mockResolvedValueOnce({ deleted: true });
    fireEvent.click(screen.getByRole("button", { name: "Báo thiếu thông tin" }));
    fireEvent.change(await screen.findByLabelText(/Câu hỏi/), { target: { value: "Học phí kỳ này nộp ở đâu?" } });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
    expect(await screen.findByText("ma-xoa-123")).toBeInTheDocument();
    expect(post).toHaveBeenCalledWith("/v1/answer-gap-reports", { question: "Học phí kỳ này nộp ở đâu?", consent: true, consent_version: GAP_CONSENT_VERSION });
    fireEvent.click(screen.getByRole("button", { name: "Xóa báo cáo này" }));
    await waitFor(() => expect(screen.getByText("Báo cáo đã được xóa.")).toBeInTheDocument());
    expect(post).toHaveBeenLastCalledWith("/v1/answer-gap-reports/delete", { delete_code: "ma-xoa-123" });
  });

  it("says nothing was saved when sending fails", async () => {
    const post = setup();
    post.mockRejectedValueOnce(new Error("503"));
    fireEvent.click(screen.getByRole("button", { name: "Báo thiếu thông tin" }));
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Gửi" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Chưa có gì được lưu");
  });

  it("is available in English", async () => {
    setup("en");
    fireEvent.click(screen.getByRole("button", { name: "Report missing information" }));
    expect(await screen.findByText("Send this question to staff so they can add the missing information?")).toBeInTheDocument();
    expect(screen.getByText(/How long: 90 days/)).toBeInTheDocument();
  });
});
