import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const http = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../lib/api/client", () => ({ ApiClient: class { get = http.get; post = http.post; } }));
vi.mock("../../lib/features", () => ({ FeatureGate: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
import { PolicyImpact } from "./PolicyImpact";

beforeEach(() => { http.get.mockReset(); http.post.mockReset(); });
afterEach(cleanup);

describe("PolicyImpact", () => {
  it("shows what changed by severity, the number change and the rules to review, and conflicting facts", async () => {
    http.get.mockImplementation((path: string) => path === "/v1/policy-conflicts"
      ? Promise.resolve({ count: 1, items: [{ code: "FACT_VALUE_CONFLICT", kind: "fee", subject: "Học phí CLC", a: { value: "533.000", quote: "A" }, b: { value: "580.500", quote: "B" } }] })
      : Promise.resolve({ old_release: "r1", new_release: "r2", status: "ANALYZED", summary: { by_severity: { HIGH: 1 } },
          items: [{ status: "MODIFIED", labels: ["NUMERIC"], severity: "HIGH", renumbered: false, family: "quy_che", path: "Điều 9 > Khoản 3", similarity: 0.9, numeric: [{ old: "20%", new: "25%" }] }],
          dependencies: { rules: [{ rule_id: "attendance-requirement" }], eval_cases: [] } }));
    render(<PolicyImpact />);
    expect(await screen.findByText(/1 mức Cao/)).toBeTruthy();
    expect(screen.getByText("20% → 25%")).toBeTruthy();
    expect(screen.getByText(/1 luật trích đoạn đã đổi, cần rà lại: attendance-requirement/)).toBeTruthy();
    expect(await screen.findByText(/một nguồn ghi «533.000», nguồn khác ghi «580.500»/)).toBeTruthy();
  });

  it("explains the first snapshot and an empty conflict list", async () => {
    http.get.mockImplementation((path: string) => path === "/v1/policy-conflicts" ? Promise.resolve({ count: 0, items: [] })
      : Promise.resolve({ old_release: null, new_release: "r1", status: "BASELINE_ONLY", summary: {}, items: [], dependencies: {} }));
    render(<PolicyImpact />);
    expect(await screen.findByText(/Đây là ảnh chụp đầu tiên/)).toBeTruthy();
    expect(await screen.findByText(/Không thấy hai nguồn nào ghi khác nhau/)).toBeTruthy();
  });
});
