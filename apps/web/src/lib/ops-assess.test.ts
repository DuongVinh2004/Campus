import { describe, expect, it } from "vitest";
import { assessStatus, overallLevel, THRESHOLDS, type Finding } from "./ops-assess";
import type { OpsStatus, OpsWindow } from "./ops-status-api";

const window = (over: Partial<OpsWindow> = {}): OpsWindow => ({
  minutes: 5, turns: 50, ok: 48, abstained: 2, errors: {}, error_rate: 0, p50_s_le: 5, p95_s_le: 12, first_token_p95_s_le: 3,
  admission_rejected: 0, admission_rejected_rate: 0, rate_limited: {}, loop_blocked: 0, loop_blocked_max_ms: 0, ...over,
});

function status(over: Partial<OpsStatus> & { five?: Partial<OpsWindow>; ten?: Partial<OpsWindow> } = {}): OpsStatus {
  const { five, ten, ...rest } = over;
  return {
    generated_at: "2026-11-17T03:00:00Z", workers_reporting: 2, window_minutes: 60,
    turns: { last_5m: window(five), last_10m: window({ minutes: 10, ...ten }), last_60m: window({ minutes: 60 }) },
    load: { in_flight: 4, waiting: 0, limit: 32 },
    retrieval: { retrievals: 100, failed: 1, timeouts: 0, failed_rate: 0.01, vector_ms_max: 900 },
    models: { embedding: "up", reranker: "up" },
    gateway: { reachable: true, today: { usd: "1.21", calls: 940, usd_cap: "5.00", call_cap: 2000, cap_enabled: true, cap_reached: false } },
    background: { leader: true, learning_worker: "ready" },
    storage: { data_free_pct: 41.2, backup_free_pct: 41.2 },
    backup: { configured: true, last: { at: "2026-11-17T03:12:00Z", ok: true, age_hours: 5 }, offsite: { at: "x", ok: true, age_hours: 5 }, rehearsal: null },
    series: { minute: [], turns: [], errors: [], p95_s_le: [] },
    ...rest,
  };
}

const find = (findings: Finding[], id: string) => findings.find((f) => f.id === id)!;

describe("assessStatus", () => {
  it("is all green for a healthy system", () => {
    const findings = assessStatus(status());
    expect(findings.map((f) => f.level).filter((l) => l !== "ok")).toEqual([]);
    expect(overallLevel(findings)).toBe("ok");
  });

  it("flags p95 above the threshold only when enough turns are behind it", () => {
    expect(find(assessStatus(status({ ten: { p95_s_le: 20, turns: 80 } })), "p95").level).toBe("warn");
    expect(find(assessStatus(status({ ten: { p95_s_le: 20, turns: 5 } })), "p95").level).toBe("unknown");
    expect(find(assessStatus(status({ ten: { p95_s_le: THRESHOLDS.p95SecondsWarn, turns: 80 } })), "p95").level).toBe("ok");
  });

  it("treats the overflow bucket (null with a flag) as slow, with a readable value", () => {
    const item = find(assessStatus(status({ ten: { p95_s_le: null, p95_s_le_over: 30, turns: 80 } })), "p95");
    expect(item.level).toBe("warn");
    expect(item.value).toBe("> 30 giây");
  });

  it("flags error rate over 2 % and lists the codes", () => {
    const item = find(assessStatus(status({ ten: { turns: 100, error_rate: 0.03, errors: { AI_WORKFLOW_UNAVAILABLE: 3 } } })), "errors");
    expect(item.level).toBe("warn");
    expect(item.detail).toBe("AI_WORKFLOW_UNAVAILABLE: 3");
    expect(item.value).toBe("3,0%");
    expect(find(assessStatus(status({ ten: { turns: 10, error_rate: 0.5 } })), "errors").level).toBe("unknown");
  });

  it("flags busy refusals, the lost vector branch and a long event-loop block", () => {
    const findings = assessStatus(status({
      five: { turns: 50, admission_rejected: 5, admission_rejected_rate: 5 / 55, loop_blocked: 1, loop_blocked_max_ms: 3400 },
      retrieval: { retrievals: 100, failed: 10, timeouts: 8, failed_rate: 0.1, vector_ms_max: 1200 },
    }));
    expect(["busy", "vector", "loop"].map((id) => find(findings, id).level)).toEqual(["warn", "warn", "warn"]);
  });

  it("is critical when a model server is down or no worker reports", () => {
    expect(find(assessStatus(status({ models: { embedding: "up", reranker: "down" } })), "models").level).toBe("crit");
    const none = assessStatus(status({ workers_reporting: 0 }));
    expect(find(none, "workers").level).toBe("crit");
    expect(overallLevel(none)).toBe("crit");
  });

  it("judges the gateway: unreachable is critical, near the cap warns, at the cap is critical", () => {
    const base = { usd: "1.00", calls: 100, usd_cap: "5.00", call_cap: 2000, cap_enabled: true, cap_reached: false };
    expect(find(assessStatus(status({ gateway: { reachable: false, reason: "unreachable" } })), "gateway").level).toBe("crit");
    expect(find(assessStatus(status({ gateway: { reachable: true, today: { ...base, calls: 1600 } } })), "gateway").level).toBe("warn");
    expect(find(assessStatus(status({ gateway: { reachable: true, today: { ...base, usd: "4.10" } } })), "gateway").level).toBe("warn");
    const reached = find(assessStatus(status({ gateway: { reachable: true, today: { ...base, cap_reached: true } } })), "gateway");
    expect(reached.level).toBe("crit");
    expect(reached.detail).toContain("chạm trần");
    expect(find(assessStatus(status({ gateway: { reachable: null } })), "gateway").level).toBe("unknown");
  });

  it("handles a gateway without a daily cap", () => {
    const item = find(assessStatus(status({ gateway: { reachable: true, today: { usd: "1.00", calls: 5, usd_cap: "0", call_cap: 0, cap_enabled: false, cap_reached: false } } })), "gateway");
    expect(item.level).toBe("ok");
  });

  it("grades free disk space", () => {
    const level = (pct: number | null) => find(assessStatus(status({ storage: { data_free_pct: pct, backup_free_pct: null } })), "disk").level;
    expect([level(40), level(14.9), level(4.9), level(null)]).toEqual(["ok", "warn", "crit", "unknown"]);
  });

  it("grades backups: stale, failed, missing and not configured", () => {
    const level = (backup: OpsStatus["backup"]) => find(assessStatus(status({ backup })), "backup");
    expect(level({ configured: false }).level).toBe("unknown");
    expect(level({ configured: true, last: null }).level).toBe("warn");
    expect(level({ configured: true, last: { at: "x", ok: true, age_hours: 27 } }).level).toBe("warn");
    expect(level({ configured: true, last: { at: "x", ok: false, age_hours: 2 } }).value).toContain("lỗi");
    expect(level({ configured: true, last: { at: "x", ok: true, age_hours: 2 }, rehearsal: { at: "y", ok: false, age_hours: 100 } }).level).toBe("warn");
    expect(level({ configured: true, last: { at: "x", ok: true, age_hours: 2 } }).detail).toContain("ngoài máy");
  });

  it("judges the nightly retrieval check: regression warns, skipped and never-ran are unknown, absent shows no tile", () => {
    const quality = (over: object) => find(assessStatus(status({ quality: { configured: true, ran: true, ok: true, has_baseline: true, regressions: [], metrics: { cases: 120, any: 0.95, fused_top8: 0.9, survive: 0.85 }, ...over } })), "quality");
    expect(quality({}).level).toBe("ok");
    expect(quality({}).value).toBe("top 8: 90,0%");
    expect(quality({ regressions: ["fused_top8 fell 4.0 points"] }).level).toBe("warn");
    expect(quality({ regressions: ["fused_top8 fell 4.0 points"] }).detail).toBe("fused_top8 fell 4.0 points");
    expect(quality({ ran: false, metrics: null }).level).toBe("unknown");
    const skipped = quality({ ok: false, skipped: "models_down", metrics: null });
    expect(skipped.level).toBe("unknown");
    expect(skipped.detail).toContain("Model embedding/rerank không chạy");
    expect(quality({ has_baseline: false }).detail).toBe("Chưa có mốc so sánh.");
    expect(assessStatus(status()).some((f) => f.id === "quality")).toBe(false);
    expect(assessStatus(status({ quality: { configured: false } })).some((f) => f.id === "quality")).toBe(false);
  });

  it("overall level is the worst finding, unknown only when nothing is known", () => {
    expect(overallLevel([])).toBe("unknown");
    expect(overallLevel([{ id: "a", label: "", value: "", level: "unknown" }, { id: "b", label: "", value: "", level: "warn" }])).toBe("warn");
  });
});
