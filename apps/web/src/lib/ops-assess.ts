import type { OpsStatus } from "./ops-status-api";

export type Level = "ok" | "warn" | "crit" | "unknown";

export interface Finding {
  id: string;
  label: string;
  value: string;
  detail?: string;
  level: Level;
}

/**
 * Thresholds. They are the same numbers as the alert rules in the design (docs/GROUP_A_IMPLEMENTATION_PLAN_20261117.md, A3),
 * so a tile turns amber at the moment an alert would fire. A rate is judged only with enough samples behind it.
 */
export const THRESHOLDS = {
  p95SecondsWarn: 15,
  errorRateWarn: 0.02,
  admissionRateWarn: 0.02,
  minTurnsForRate: 20,
  vectorFailedRateWarn: 0.05,
  minRetrievalsForRate: 25,
  loopBlockedMsWarn: 3000,
  capNearFraction: 0.8,
  diskWarnPct: 15,
  diskCritPct: 5,
  backupMaxAgeHours: 26,
} as const;

const pct = (value: number) => `${(value * 100).toFixed(1).replace(".", ",")}%`;

function rate(value: number, samples: number, minimum: number, warn: number): Level {
  if (samples < minimum) return "unknown";
  return value > warn ? "warn" : "ok";
}

function worst(levels: Level[]): Level {
  for (const level of ["crit", "warn", "ok"] as const) if (levels.includes(level)) return level;
  return "unknown";
}

/** Turns the status document into the tiles of the operations page. Pure: same input, same tiles. */
export function assessStatus(status: OpsStatus): Finding[] {
  const five = status.turns.last_5m;
  const ten = status.turns.last_10m;
  const findings: Finding[] = [];

  const workers = status.workers_reporting;
  findings.push({ id: "workers", label: "Tiến trình API", value: String(workers), level: workers > 0 ? "ok" : "crit",
    detail: workers > 0 ? undefined : "Không có tiến trình nào báo số liệu trong 60 giây gần nhất." });

  findings.push({ id: "turns", label: "Lượt hỏi (5 phút)", value: String(five.turns), level: "ok",
    detail: `${five.abstained} lượt từ chối có chủ đích` });

  const p95 = ten.p95_s_le;
  const p95Level: Level = ten.turns < THRESHOLDS.minTurnsForRate ? "unknown"
    : p95 === null ? (ten.p95_s_le_over ? "warn" : "unknown") : p95 > THRESHOLDS.p95SecondsWarn ? "warn" : "ok";
  findings.push({ id: "p95", label: "p95 thời gian trả lời (10 phút)", level: p95Level,
    value: ten.p95_s_le !== null ? `≤ ${ten.p95_s_le} giây` : ten.p95_s_le_over ? `> ${ten.p95_s_le_over} giây` : "—" });

  findings.push({ id: "errors", label: "Tỉ lệ lỗi (10 phút)", value: ten.turns ? pct(ten.error_rate) : "—",
    level: rate(ten.error_rate, ten.turns, THRESHOLDS.minTurnsForRate, THRESHOLDS.errorRateWarn),
    detail: Object.entries(ten.errors).map(([code, count]) => `${code}: ${count}`).join(", ") || undefined });

  findings.push({ id: "busy", label: "Quá tải 503 (5 phút)", value: String(five.admission_rejected),
    level: rate(five.admission_rejected_rate, five.turns + five.admission_rejected, THRESHOLDS.minTurnsForRate, THRESHOLDS.admissionRateWarn),
    detail: `Đang xử lý ${status.load.in_flight}/${status.load.limit}, chờ ${status.load.waiting}` });

  findings.push({ id: "vector", label: "Nhánh vector bị mất", value: status.retrieval.retrievals ? pct(status.retrieval.failed_rate) : "—",
    level: rate(status.retrieval.failed_rate, status.retrieval.retrievals, THRESHOLDS.minRetrievalsForRate, THRESHOLDS.vectorFailedRateWarn) });

  findings.push({ id: "loop", label: "Vòng lặp bị chặn (5 phút)", value: five.loop_blocked ? `${five.loop_blocked_max_ms} ms` : "0",
    level: five.loop_blocked_max_ms >= THRESHOLDS.loopBlockedMsWarn ? "warn" : "ok" });

  const models = Object.entries(status.models);
  findings.push({ id: "models", label: "Model embedding / rerank", level: models.length === 0 ? "unknown" : models.some(([, s]) => s !== "up") ? "crit" : "ok",
    value: models.length ? models.map(([name, state]) => `${name}: ${state === "up" ? "chạy" : "ngừng"}`).join(" · ") : "chưa cấu hình" });

  const gateway = status.gateway;
  const today = gateway.today ?? null;
  let gatewayLevel: Level = gateway.reachable === null ? "unknown" : gateway.reachable ? "ok" : "crit";
  let gatewayValue = gateway.reachable === null ? "chưa cấu hình" : gateway.reachable ? "kết nối được" : "không kết nối được";
  let gatewayDetail: string | undefined;
  if (gateway.reachable && today?.cap_enabled) {
    const usdUsed = Number(today.usd) / (Number(today.usd_cap) || Infinity);
    const callsUsed = today.call_cap ? today.calls / today.call_cap : 0;
    const used = Math.max(Number.isFinite(usdUsed) ? usdUsed : 0, callsUsed);
    gatewayLevel = today.cap_reached ? "crit" : used >= THRESHOLDS.capNearFraction ? "warn" : "ok";
    gatewayValue = `${today.calls}/${today.call_cap || "∞"} lời gọi · $${today.usd}/${Number(today.usd_cap) ? today.usd_cap : "∞"}`;
    gatewayDetail = today.cap_reached ? "Đã chạm trần trong ngày: lượt mới bị từ chối." : undefined;
  }
  findings.push({ id: "gateway", label: "Chi phí hôm nay", value: gatewayValue, level: gatewayLevel, detail: gatewayDetail });

  const quality = status.quality;
  if (quality?.configured) {
    const metrics = quality.metrics;
    const regressions = quality.regressions ?? [];
    findings.push({
      id: "quality",
      label: "Chất lượng truy hồi (đêm qua)",
      value: !quality.ran ? "chưa chạy lần nào" : quality.skipped ? "bị bỏ qua" : metrics ? `top 8: ${pct(metrics.fused_top8)}` : "—",
      level: !quality.ran || quality.skipped || !quality.ok ? "unknown" : regressions.length ? "warn" : "ok",
      detail: regressions[0] ?? (quality.skipped === "models_down" ? "Model embedding/rerank không chạy nên không kiểm được." : quality.ran && !quality.has_baseline ? "Chưa có mốc so sánh." : undefined),
    });
  }

  const data = status.storage.data_free_pct;
  findings.push({ id: "disk", label: "Dung lượng trống", value: data === null ? "—" : `${String(data).replace(".", ",")}%`,
    level: data === null ? "unknown" : data < THRESHOLDS.diskCritPct ? "crit" : data < THRESHOLDS.diskWarnPct ? "warn" : "ok" });

  const backup = status.backup;
  if (!backup.configured) {
    findings.push({ id: "backup", label: "Sao lưu", value: "chưa cấu hình", level: "unknown" });
  } else {
    const records = [backup.last, backup.offsite, backup.rehearsal].filter((r): r is NonNullable<typeof r> => r != null);
    const lastLevel: Level = !backup.last ? "warn" : !backup.last.ok || (backup.last.age_hours ?? Infinity) > THRESHOLDS.backupMaxAgeHours ? "warn" : "ok";
    const failed = records.some((record) => !record.ok);
    findings.push({ id: "backup", label: "Sao lưu", level: worst([lastLevel, failed ? "warn" : "ok"]),
      value: backup.last ? `${backup.last.age_hours ?? "?"} giờ trước${backup.last.ok ? "" : " (lỗi)"}` : "chưa có bản nào",
      detail: backup.offsite ? undefined : "Chưa có bản sao ngoài máy." });
  }
  const features = status.features;
  if (features) {
    const ending = features.expiring_soon ?? [];
    const level: Level = features.store_error ? "crit" : features.restart_required || ending.length ? "warn" : "ok";
    findings.push({ id: "features", label: "Cờ tính năng", level,
      value: `${features.off} tắt · ${features.overrides} ghi đè`,
      detail: features.store_error ? "Không đọc được kho cờ: đang dùng giá trị mặc định."
        : [features.restart_required ? `${features.restart_required} cờ cần khởi động lại mới có tác dụng.` : "",
           ending.length ? `Sắp hết hạn trong 24 giờ: ${ending.map((e) => e.key).join(", ")}.` : ""].filter(Boolean).join(" ") || undefined });
  }
  return findings;
}

/** The single most urgent level on the page, for the page header. */
export function overallLevel(findings: Finding[]): Level {
  return worst(findings.map((finding) => finding.level));
}
