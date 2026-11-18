import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PolicyGraphReview, type GraphView } from "./PolicyGraphReview";
afterEach(cleanup);
function view(): GraphView {
  const source = { source_id: "s", document_version_id: "v", chunk_id: "c", content_sha256: "a".repeat(64), locator: { page_start: 39 }, quote: "Đây là đoạn nguồn nguyên văn, gồm đủ điều kiện." };
  return { proposal: { id: "candidate-v1", origin: "llm_candidate", index_fingerprint: "i", source_fingerprint: "s",
    nodes: [{ id: "p", kind: "Procedure", label: "Xác nhận", aliases: [], source, operator: null, members: [], qualifiers: [] },
      { id: "g", kind: "ConditionGroup", label: "Nhóm điều kiện", aliases: [], source, operator: "ALL", members: ["p"], qualifiers: [] }],
    edges: [{ id: "e", from_id: "p", to_id: "g", relation: "requires", source, scope: { audiences: ["STUDENT"], faculties: ["PUBLIC"], programs: ["PUBLIC"] }, interval: { status: "unknown", start: null, end: null } }] },
    reviews: [], issues: [], revision: 0, publication: null, raw_proposal: '{"candidate":true}' };
}
describe("Policy graph source review", () => {
  it("shows original source, ALL, unknown legal dates and unreviewed state", () => {
    render(<PolicyGraphReview view={view()} onReview={vi.fn()} onPreview={vi.fn()} onPublish={vi.fn()} />);
    expect(screen.getByText(/ALL — cần đủ mọi điều kiện/)).toBeTruthy();
    expect(screen.getByText("Chưa xác minh ngày hiệu lực")).toBeTruthy();
    expect(screen.getByText(view().proposal.edges[0].source.quote)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Xem trước xuất bản" }) as HTMLButtonElement).disabled).toBe(true);
  });
  it("only submits review after a note and surfaces server failures", async () => {
    const onReview = vi.fn().mockRejectedValue(new Error("conflict"));
    render(<PolicyGraphReview view={view()} onReview={onReview} onPreview={vi.fn()} onPublish={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Ghi nhận đối chiếu nguồn, điều kiện và hiệu lực"), { target: { value: "Đã đối chiếu đoạn gốc" } });
    fireEvent.click(screen.getByText("Duyệt quan hệ"));
    await waitFor(() => expect(onReview).toHaveBeenCalledWith("e", "approved", "Đã đối chiếu đoạn gốc", 0));
    expect(await screen.findByRole("alert")).toBeTruthy();
  });
  it("requires a preview then a separate explicit publication confirmation", async () => {
    const v = view(); v.revision = 3;
    v.reviews = ["p", "g", "e"].map((target, i) => ({ target, verdict: "approved", reviewer: "admin", note: "checked", revision: i+1 }));
    const onPreview = vi.fn().mockResolvedValue({ confirmation: "h", preview: {} }), onPublish = vi.fn();
    render(<PolicyGraphReview view={v} onReview={vi.fn()} onPreview={onPreview} onPublish={onPublish} />);
    fireEvent.click(screen.getByText("Xem trước xuất bản"));
    await screen.findByText("Xác nhận xuất bản phiên bản này");
    expect(onPublish).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Xác nhận xuất bản phiên bản này"));
    await waitFor(() => expect(onPublish).toHaveBeenCalledWith(3, "h"));
  });
  it("published immutable versions cannot be reviewed again", () => {
    const v = view(); v.publication = { graph_id: "candidate-v1" };
    render(<PolicyGraphReview view={v} onReview={vi.fn()} onPreview={vi.fn()} onPublish={vi.fn()} />);
    expect(screen.queryByText("Duyệt quan hệ")).toBeNull();
  });
});
