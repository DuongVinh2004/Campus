import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { LanguageProvider } from "../../lib/i18n";
import { AnswerFeedback } from "./AnswerFeedback";
import { CitationDrawer } from "./CitationDrawer";

vi.mock("../../lib/use-source-review-states", () => ({ useSourceReviewStates: () => ({}) }));
beforeEach(() => { document.cookie = "lang=en; path=/"; });
afterEach(() => { cleanup(); document.cookie = "lang=; path=/; max-age=0"; });

describe("chat parts in English", () => {
  it("translates the rating question and buttons", () => {
    render(<LanguageProvider><AnswerFeedback answerId="m" onFeedbackSubmit={vi.fn()} /></LanguageProvider>);
    expect(screen.getByText("Was this answer helpful?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Helpful" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Not helpful" })).toBeInTheDocument();
  });

  it("translates the citation drawer chrome and keeps the source's own text", () => {
    render(<LanguageProvider><CitationDrawer isOpen onClose={() => {}} citations={[{ id: "c", title: "Quy chế Đào tạo", documentRef: "QĐ-1", quote: "Nội dung điều khoản", validityStatus: "active" }]} /></LanguageProvider>);
    expect(screen.getByText("Cited sources & evidence")).toBeInTheDocument();
    expect(screen.getByText("Quy chế Đào tạo")).toBeInTheDocument();
    expect(screen.getByText("Nội dung điều khoản", { exact: false })).toBeInTheDocument();
  });
});
