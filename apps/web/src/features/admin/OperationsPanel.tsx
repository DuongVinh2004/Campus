"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, CircleHelp, RefreshCw, ShieldAlert, XOctagon } from "lucide-react";
import { ApiClientError } from "../../lib/api/client";
import { IconButton } from "@/components/shared/IconButton";
import { assessStatus, overallLevel, type Finding, type Level } from "../../lib/ops-assess";
import { opsStatusApi, type OpsStatus } from "../../lib/ops-status-api";

const REFRESH_MS = 30_000;
const TIME_ZONE = "Asia/Ho_Chi_Minh";

const LEVEL_TEXT: Record<Level, string> = { ok: "Bình thường", warn: "Cần chú ý", crit: "Nghiêm trọng", unknown: "Chưa đủ dữ liệu" };
const LEVEL_STYLE: Record<Level, string> = {
  ok: "border-[var(--color-success,#1a7f37)]",
  warn: "border-[var(--color-warning,#b7791f)]",
  crit: "border-[var(--color-danger,#c0392b)]",
  unknown: "border-[var(--border-subtle,#d0d5dd)]",
};

function LevelIcon({ level }: { level: Level }) {
  const common = { className: "h-4 w-4 shrink-0", "aria-hidden": true } as const;
  if (level === "ok") return <CheckCircle2 {...common} />;
  if (level === "warn") return <AlertTriangle {...common} />;
  if (level === "crit") return <XOctagon {...common} />;
  return <CircleHelp {...common} />;
}

function time(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("vi-VN", { timeZone: TIME_ZONE, hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(date);
}

/** Two small line charts drawn as SVG paths; no chart library. `null` points leave a gap. */
export function Sparkline({ values, label, max }: { values: Array<number | null>; label: string; max?: number }) {
  const width = 240;
  const height = 48;
  const ceiling = max ?? Math.max(1, ...values.map((v) => v ?? 0));
  const step = values.length > 1 ? width / (values.length - 1) : width;
  let path = "";
  let pen = false;
  values.forEach((value, index) => {
    if (value === null) {
      pen = false;
      return;
    }
    const x = (index * step).toFixed(1);
    const y = (height - 2 - (Math.min(value, ceiling) / ceiling) * (height - 4)).toFixed(1);
    path += `${pen ? "L" : "M"}${x} ${y} `;
    pen = true;
  });
  return (
    <svg role="img" aria-label={label} viewBox={`0 0 ${width} ${height}`} className="h-12 w-full" preserveAspectRatio="none">
      <path d={path.trim() || `M0 ${height - 2}`} fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function Tile({ finding }: { finding: Finding }) {
  return (
    <li data-testid={`ops-${finding.id}`} data-level={finding.level}
        className={`campus-panel min-w-0 border-l-4 p-4 ${LEVEL_STYLE[finding.level]}`}>
      <p className="text-xs font-medium text-[var(--text-secondary)]">{finding.label}</p>
      <p className="mt-1 break-words text-lg font-semibold text-[var(--text-primary)]">{finding.value}</p>
      <p className="mt-1 flex items-center gap-1.5 text-xs text-[var(--text-secondary)]">
        <LevelIcon level={finding.level} />
        <span>{LEVEL_TEXT[finding.level]}</span>
      </p>
      {finding.detail ? <p className="mt-1 break-words text-xs text-[var(--text-secondary)]">{finding.detail}</p> : null}
    </li>
  );
}

export function OperationsPanel({ refreshMs = REFRESH_MS }: { refreshMs?: number }) {
  const [status, setStatus] = useState<OpsStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [loading, setLoading] = useState(true);
  const inFlight = useRef(false);

  const load = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      setStatus(await opsStatusApi.get());
      setError(null);
    } catch (caught) {
      if (caught instanceof ApiClientError && caught.problem.status === 403) setForbidden(true);
      else setError(caught instanceof ApiClientError ? caught.message : "Không tải được trạng thái vận hành.");
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void load();
    }, refreshMs);
    const onVisible = () => {
      if (document.visibilityState === "visible") void load();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [load, refreshMs]);

  if (forbidden) {
    return (
      <section data-testid="ops-forbidden" role="alert" className="campus-panel flex items-center gap-3 p-6">
        <ShieldAlert className="h-6 w-6" aria-hidden="true" />
        <p className="text-sm">Chỉ quản trị viên mới xem được trạng thái vận hành.</p>
      </section>
    );
  }
  if (loading && !status) {
    return (
      <section data-testid="ops-loading" role="status" className="campus-panel flex items-center gap-3 p-6 text-[var(--text-secondary)]">
        <RefreshCw className="h-5 w-5 animate-spin" aria-hidden="true" />
        <p className="text-sm">Đang tải trạng thái vận hành…</p>
      </section>
    );
  }
  if (!status) {
    return (
      <section data-testid="ops-error" role="alert" className="campus-panel space-y-3 p-6">
        <p className="text-sm">{error}</p>
        <button type="button" onClick={() => void load()}
                className="inline-flex min-h-[44px] items-center rounded-lg bg-[var(--color-primary)] px-5 py-2.5 text-sm font-medium text-[var(--color-on-primary)]">
          Thử lại
        </button>
      </section>
    );
  }

  const findings = assessStatus(status);
  const overall = overallLevel(findings);
  const series = status.series;
  return (
    <section data-testid="ops-panel" aria-labelledby="ops-heading" className="min-w-0 space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 id="ops-heading" className="text-xl font-semibold text-[var(--text-primary)]">Vận hành hệ thống</h2>
          <p data-testid="ops-overall" data-level={overall} className="text-sm text-[var(--text-secondary)]">
            {LEVEL_TEXT[overall]} · cập nhật {time(status.generated_at)} · {status.workers_reporting} tiến trình API
          </p>
        </div>
        <IconButton label="Làm mới trạng thái vận hành" variant="outline" onClick={() => void load()} icon={<RefreshCw size={18} />} />
      </header>
      {error ? <p role="alert" className="text-sm text-[var(--color-danger,#c0392b)]">Không làm mới được: {error}. Đang hiện số liệu lần trước.</p> : null}
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {findings.map((finding) => <Tile key={finding.id} finding={finding} />)}
      </ul>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <figure className="campus-panel p-4">
          <figcaption className="text-xs font-medium text-[var(--text-secondary)]">Lượt hỏi mỗi phút (60 phút)</figcaption>
          <Sparkline values={series.turns} label="Số lượt hỏi mỗi phút trong 60 phút gần nhất" />
        </figure>
        <figure className="campus-panel p-4">
          <figcaption className="text-xs font-medium text-[var(--text-secondary)]">Lượt lỗi mỗi phút (60 phút)</figcaption>
          <Sparkline values={series.errors} label="Số lượt lỗi mỗi phút trong 60 phút gần nhất" />
        </figure>
      </div>
    </section>
  );
}
