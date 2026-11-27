import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ list: vi.fn() }));
vi.mock("../../lib/procedures-api", () => ({ proceduresApi: api }));
import { MyProcedures } from "./MyProcedures";

afterEach(cleanup);

const run = (id: string, state: string, extra: object = {}) => ({ id, procedure_id: "student-certificate", title: "Giấy xác nhận sinh viên", state,
  fields: {}, field_origin: {}, blocked: [], missing: [], row_version: 1, next_step: "", ticket: null, expires_at: "2026-12-26T00:00:00Z", ...extra });

describe("MyProcedures", () => {
  it("puts unfinished procedures first with a link to continue, and sent ones with their ticket code", async () => {
    api.list.mockResolvedValue({ items: [run("r1", "SUBMITTED", { ticket: { id: "t", code: "HS-2026-000213" } }), run("r2", "COLLECTING"), run("r3", "CANCELLED")] });
    render(<MyProcedures />);
    const items = await screen.findAllByRole("listitem");
    expect(items.map(i => i.textContent?.split(" · ")[1])).toEqual(["Đang điền", "Đã gửi", "Đã hủy"]);
    expect(screen.getByRole("link", { name: "Làm tiếp" }).getAttribute("href")).toBe("/services/procedures?run=r2");
    expect(items[1].textContent).toContain("mã hồ sơ HS-2026-000213");
  });

  it("does not offer to continue the procedure that is open on the page", async () => {
    api.list.mockResolvedValue({ items: [run("r2", "COLLECTING")] });
    render(<MyProcedures currentRunId="r2" />);
    await screen.findByText(/Đang điền/);
    expect(screen.queryByRole("link", { name: "Làm tiếp" })).toBeNull();
  });

  it("says so when there is none", async () => {
    api.list.mockResolvedValue({ items: [] });
    render(<MyProcedures />);
    expect(await screen.findByText("Bạn chưa bắt đầu thủ tục nào.")).toBeTruthy();
  });
});
