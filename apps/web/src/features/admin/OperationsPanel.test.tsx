import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ApiClientError } from "@/lib/api/client";
import { OperationsPanel, Sparkline } from "./OperationsPanel";
import { opsStatusApi, type OpsStatus, type OpsWindow } from "@/lib/ops-status-api";

vi.mock("@/lib/ops-status-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/ops-status-api")>("@/lib/ops-status-api");
  return { ...actual, opsStatusApi: { get: vi.fn() } };
});

const window5 = (over: Partial<OpsWindow> = {}): OpsWindow => ({
  minutes: 5, turns: 50, ok: 48, abstained: 2, errors: {}, error_rate: 0, p50_s_le: 5, p95_s_le: 12, first_token_p95_s_le: 3,
  admission_rejected: 0, admission_rejected_rate: 0, rate_limited: {}, loop_blocked: 0, loop_blocked_max_ms: 0, ...over,
});

const healthy: OpsStatus = {
  generated_at: "2026-11-17T03:00:00Z", workers_reporting: 2, window_minutes: 60,
  turns: { last_5m: window5(), last_10m: window5({ minutes: 10 }), last_60m: window5({ minutes: 60 }) },
  load: { in_flight: 4, waiting: 0, limit: 32 },
  retrieval: { retrievals: 100, failed: 1, timeouts: 0, failed_rate: 0.01, vector_ms_max: 900 },
  models: { embedding: "up", reranker: "up" },
  gateway: { reachable: true, today: { usd: "1.21", calls: 940, usd_cap: "5.00", call_cap: 2000, cap_enabled: true, cap_reached: false } },
  background: { leader: true, learning_worker: "ready" },
  storage: { data_free_pct: 41.2, backup_free_pct: 41.2 },
  backup: { configured: true, last: { at: "2026-11-17T03:12:00Z", ok: true, age_hours: 5 }, offsite: null, rehearsal: null },
  series: { minute: [0, 60, 120], turns: [0, 5, 9], errors: [0, 0, 1], p95_s_le: [null, 5, 8] },
};

const get = vi.mocked(opsStatusApi.get);

// Braces matter: a function returned from beforeEach is run by vitest as cleanup, which would call the mock itself.
beforeEach(() => {
  get.mockReset();
});
afterEach(cleanup);

describe("OperationsPanel", () => {
  it("shows a loading state, then every tile with its level", async () => {
    get.mockResolvedValue(healthy);
    render(<OperationsPanel />);
    expect(screen.getByTestId("ops-loading")).toBeDefined();
    await screen.findByTestId("ops-panel");
    expect(screen.getAllByRole("listitem").length).toBeGreaterThanOrEqual(10);
    expect(screen.getByTestId("ops-turns").textContent).toContain("50");
    expect(screen.getByTestId("ops-gateway").textContent).toContain("940/2000");
    expect(screen.getByTestId("ops-overall").getAttribute("data-level")).toBe("ok");
    expect(screen.getByRole("img", { name: /lượt hỏi mỗi phút/i })).toBeDefined();
  });

  it("marks a down model as critical", async () => {
    get.mockResolvedValue({ ...healthy, models: { embedding: "up", reranker: "down" } });
    render(<OperationsPanel />);
    await screen.findByTestId("ops-panel");
    expect(screen.getByTestId("ops-models").getAttribute("data-level")).toBe("crit");
    expect(screen.getByTestId("ops-overall").getAttribute("data-level")).toBe("crit");
    expect(screen.getByTestId("ops-models").textContent).toContain("reranker: ngừng");
  });

  it("explains that only administrators may see it on a 403", async () => {
    const denied = new ApiClientError({ type: "x", title: "Forbidden", status: 403, detail: "no", code: "FORBIDDEN" });
    get.mockImplementation(() => Promise.reject(denied));
    render(<OperationsPanel />);
    expect((await screen.findByTestId("ops-forbidden")).textContent).toContain("quản trị viên");
  });

  it("shows an error with a retry that works", async () => {
    get.mockRejectedValueOnce(new Error("network"));
    get.mockResolvedValueOnce(healthy);
    render(<OperationsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Thử lại" }));
    await screen.findByTestId("ops-panel");
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("keeps the last numbers when a refresh fails and says so", async () => {
    get.mockResolvedValueOnce(healthy);
    render(<OperationsPanel />);
    await screen.findByTestId("ops-panel");
    get.mockRejectedValueOnce(new Error("network"));
    fireEvent.click(screen.getByRole("button", { name: /làm mới/i }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("lần trước"));
    expect(screen.getByTestId("ops-panel")).toBeDefined();
  });

  it("refreshes on a timer while the tab is visible and not while it is hidden", async () => {
    vi.useFakeTimers();
    try {
      get.mockResolvedValue(healthy);
      render(<OperationsPanel refreshMs={1000} />);
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      const first = get.mock.calls.length;
      await act(async () => { await vi.advanceTimersByTimeAsync(2100); });
      expect(get.mock.calls.length).toBeGreaterThan(first);
      const visible = vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
      const before = get.mock.calls.length;
      await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
      expect(get.mock.calls.length).toBe(before);
      visible.mockRestore();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("Sparkline", () => {
  it("draws a line per run of numbers and leaves a gap for null", () => {
    const { container } = render(<Sparkline values={[1, 2, null, 3]} label="x" />);
    const d = container.querySelector("path")!.getAttribute("d")!;
    expect(d.match(/M/g)).toHaveLength(2);
    expect(d.match(/L/g)).toHaveLength(1);
  });

  it("does not crash with no data", () => {
    const { container } = render(<Sparkline values={[]} label="x" />);
    expect(container.querySelector("path")!.getAttribute("d")).toBeTruthy();
  });
});
