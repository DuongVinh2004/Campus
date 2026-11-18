import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { ComponentProps } from "react";
import { IdeaCards } from "./IdeaCards";

const shareId = "00000000-0000-4000-8000-000000000004";
const versionId = "00000000-0000-4000-8000-000000000006";
const actorId = "00000000-0000-4000-8000-000000000008";
const inboxPath = "/v1/learning/shared-idea-cards";
const cardPath = "/v1/learning/me/idea-cards";
const shared = {
  id: shareId, card_revision: 1, idea: "Ý tưởng được cấp quyền",
  source: { offering_id: "class", version_id: versionId, page_no: 2, title: "Bài giảng", version_no: 1,
    kind: "TEXT", quote: "Đoạn chữ được cấp quyền", rects: [] },
};

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function showCards(extra: Partial<ComponentProps<typeof IdeaCards>> = {}) {
  return render(<IdeaCards actorId={actorId} canCreate onOpen={vi.fn()} onShare={vi.fn()} {...extra} />);
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

it("removes old shared content on focus and discards the direct share from a stale inbox", async () => {
  window.history.replaceState(null, "", `/learning?idea_share=${shareId}`);
  let revoked = false;
  let deny: (() => void) | undefined;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
    expect(new Headers(init.headers).get("X-Campus-Reader-Actor")).toBe(actorId);
    if (url === `${inboxPath}/${shareId}`) {
      if (!revoked) return response(shared);
      return new Promise<Response>(resolve => { deny = () => resolve(response({ code: "NOT_FOUND" }, 404)); });
    }
    if (url.startsWith(`${inboxPath}?`)) return response({ items: [shared, {
      ...shared, id: "another-share", idea: "Phiếu khác còn quyền", source: { ...shared.source, quote: "Chữ từ phiếu khác" },
    }] });
    return response({ items: [] });
  }));
  showCards();
  expect(await screen.findByText(shared.idea)).toBeVisible();
  expect(screen.getByText(shared.source.quote)).toBeVisible();
  revoked = true;
  act(() => window.dispatchEvent(new Event("focus")));
  expect(screen.queryByText(shared.idea)).toBeNull();
  expect(await screen.findByText("Phiếu khác còn quyền")).toBeVisible();
  deny?.();
  expect(await screen.findByRole("alert")).toHaveTextContent("Phiếu chia sẻ không còn khả dụng.");
  expect(screen.queryByText(shared.idea)).toBeNull();
  expect(screen.queryByText(shared.source.quote)).toBeNull();
});

it("keeps own prose when a rejected quote is replaced with a whole-page reference", async () => {
  const writes: unknown[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
    if (url === cardPath && init.method === "POST") {
      const payload = JSON.parse(String(init.body));
      writes.push(payload);
      return payload.source.kind === "TEXT" ? response({ code: "IDEA_QUOTE_UNVERIFIED" }, 422) : response({});
    }
    return response({ items: [] });
  }));
  showCards({ sourceRequest: { sequence: 1, selection: { version_id: versionId, page_no: 2,
    anchor: { kind: "TEXT", text_quote: { exact: "Chữ chưa đối chiếu" } } } } });
  expect(screen.getByRole("heading", { name: "Lưu phiếu riêng" })).toHaveFocus();
  const prose = { problem: "Vấn đề thử", idea: "Ý tưởng do tôi viết", verification: "Cách kiểm chứng thử" };
  fireEvent.change(screen.getByLabelText("Vấn đề"), { target: { value: prose.problem } });
  fireEvent.change(screen.getByLabelText("Ý tưởng"), { target: { value: prose.idea } });
  fireEvent.change(screen.getByLabelText("Cách kiểm chứng"), { target: { value: prose.verification } });
  fireEvent.click(screen.getByRole("button", { name: "Lưu phiếu ý tưởng" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Đoạn chữ chưa đối chiếu được với đúng trang.");
  fireEvent.click(screen.getByRole("button", { name: "Dẫn cả trang" }));
  expect(screen.getByLabelText("Ý tưởng")).toHaveValue(prose.idea);
  fireEvent.click(screen.getByRole("button", { name: "Lưu phiếu ý tưởng" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Đã lưu phiếu riêng.");
  expect(writes).toEqual([
    { ...prose, topic_id: null, source_description: "", source: { version_id: versionId, page_no: 2, kind: "TEXT", quote: "Chữ chưa đối chiếu" } },
    { ...prose, topic_id: null, source_description: "", source: { version_id: versionId, page_no: 2, kind: "PAGE" } },
  ]);
});
