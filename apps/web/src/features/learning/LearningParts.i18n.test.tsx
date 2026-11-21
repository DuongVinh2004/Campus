import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { LanguageProvider } from "../../lib/i18n";

const calls = vi.hoisted(() => ({ request: vi.fn(), list: vi.fn(), write: vi.fn() }));
vi.mock("../../lib/data/api/learning-gateway", () => ({
  LearningGateway: class { request = calls.request; list = calls.list; write = calls.write; },
}));

import { SessionPracticeSets } from "./PracticeSets";
import { IdeaCards } from "./IdeaCards";

const materials = [{ id: "m1", title: "Bài 1", visibility: "VISIBLE", current_published_version_id: "v1", versions: [] }] as never;

beforeEach(() => { document.cookie = "lang=en; path=/"; calls.request.mockReset(); calls.list.mockReset(); calls.write.mockReset(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); document.cookie = "lang=; path=/; max-age=0"; });

describe("learning parts in English", () => {
  it("practice sets: labels and the result messages", async () => {
    const set = { id: "s1", title: "Ôn chương 1", status: "PUBLISHED", revision: 3, item_count: 2 };
    calls.list.mockResolvedValue([set]);
    calls.request.mockResolvedValue({ ...set, items: [
      { id: "i1", kind: "single_choice", prompt: "Câu hỏi một", options: [{ id: "a", text: "Nén" }, { id: "b", text: "Kéo" }] }] });
    calls.write.mockResolvedValueOnce({ correct: true, answer: ["a"], accepted: [], explanation: "", citations: [], next_review_at: "x" });
    render(<LanguageProvider><SessionPracticeSets sessionId="ses" materials={materials} canManage={false} actorId="u" /></LanguageProvider>);
    expect(await screen.findByText("Practice questions")).toBeInTheDocument();
    expect(screen.getByText(/Ôn chương 1 · 2 questions/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Practice" }));
    expect(await screen.findByText("Question 1/1")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Nén"));
    fireEvent.click(screen.getByRole("button", { name: "Answer" }));
    expect(await screen.findByText("Correct.")).toBeInTheDocument();
  });

  it("idea cards: heading, empty state and the private card form", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "Content-Type": "application/json" } })));
    render(<LanguageProvider><IdeaCards actorId="00000000-0000-4000-8000-000000000008" canCreate onOpen={vi.fn()} onShare={vi.fn()} /></LanguageProvider>);
    expect(await screen.findByRole("heading", { name: "Idea cards" })).toBeInTheDocument();
    expect(await screen.findByText("Cards received")).toBeInTheDocument();
  });
});
