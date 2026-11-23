"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { useT, type MessageKey } from "@/lib/i18n";
import { ApiClient } from "@/lib/api/client";
import { Check, FileText, Inbox, MessageSquare, ShieldCheck } from "lucide-react";

type Notice = { version: string; effective_at: string; data_categories: string[]; purposes: string[]; retention_summary: string | Record<string, unknown>; disclaimer?: { statement?: string } };
type Consent = { id: string; purpose: string; decision: string; notice_version: string; recorded_at: string };

const LABELS: Record<string, MessageKey> = {
  ACCOUNT_CONTEXT: "privx.l0",
  CONVERSATION_CONTENT: "privx.l1",
  REQUEST_METADATA: "privx.l2",
  AUDIT_METADATA: "privx.l3",
  SERVICE_DELIVERY: "privx.l4",
  SAFETY_HANDOVER: "privx.l5",
  QUALITY_FEEDBACK: "privx.l6",
  SECURITY_AUDIT: "privx.l7",
  GRANTED: "privx.l8",
  ACCEPTED: "privx.l9",
  DENIED: "privx.l10",
  DECLINED: "privx.l11",
  WITHDRAWN: "privx.l12",
};
type T = (key: MessageKey, params?: Record<string, string | number>) => string;
const label = (code: string, t: T) => (LABELS[code] ? t(LABELS[code]) : code.toLowerCase().replace(/_/g, " "));
const retentionRows = (value: Notice["retention_summary"], t: T): string[] => {
  if (typeof value === "string") return [value];
  const items = Array.isArray(value) ? value : [value];
  return items.map(item => {
    const row = item as { data_class?: string; configured_rule?: string; retention?: string };
    return row.data_class ? `${label(row.data_class, t)}${row.retention ? `: ${row.retention}` : ""}${row.configured_rule ? ` (${t("privx.rule", { rule: row.configured_rule })})` : ""}` : JSON.stringify(item);
  });
};
export function OperationalPrivacy() {
  const t = useT();
  const [notice, setNotice] = useState<Notice | null>(null), [consents, setConsents] = useState<Consent[]>([]), [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void Promise.all([new ApiClient().get<Notice>("/v1/privacy/notice"), new ApiClient().get<{ items: Consent[] }>("/v1/privacy/consents")]).then(([value, records]) => {
      if (active) { setNotice(value); setConsents(records.items); }
    }).catch(e => { if (active) setError(e instanceof Error ? e.message : t("privx.loadError")); });
    return () => { active = false; };
  }, []);
  return <AppShell activeNav="privacy"><div className="campus-workflow space-y-5"><header className="campus-page-heading"><div><h1 className="text-2xl font-semibold">{t("privx.1")}</h1><p>{t("privx.2")}</p></div></header>
    {error && <p role="alert" className="p-4 rounded-xl border border-[var(--border-color)] text-sm">{error} <Link href="/login" className="underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]">{t("privx.3")}</Link></p>}
    {!notice && !error && <p role="status" className="text-sm py-4">{t("privx.4")}</p>}
    {notice && <section className="campus-panel space-y-5">
      <h2 className="text-lg font-semibold flex flex-wrap items-center gap-2">
        <span>{t("privx.5")} </span>
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border border-[var(--border-color)] bg-[var(--color-primary-light)] text-[var(--color-primary)]">{notice.version}</span>
      </h2>
      {notice.disclaimer?.statement ? (
        <div className="flex items-start gap-3 p-4 rounded-xl border border-[var(--border-color)] bg-[var(--color-primary-light)] text-[var(--color-primary)]">
          <ShieldCheck className="w-5 h-5 mt-0.5 shrink-0" aria-hidden="true" />
          <p className="text-sm leading-relaxed">{notice.disclaimer.statement}</p>
        </div>
      ) : null}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 rounded-xl border border-[var(--border-color)] bg-[var(--surface-card)] space-y-3">
          <h3 className="text-sm font-semibold">{t("privx.6")}</h3>
          <ul className="flex flex-wrap gap-2 list-none p-0 m-0">
            {notice.data_categories.map(item => (
              <li key={item} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-[var(--border-color)]">
                <Check className="w-3.5 h-3.5 text-[var(--color-primary)] shrink-0" aria-hidden="true" />
                {label(item, t)}
              </li>
            ))}
          </ul>
        </div>
        <div className="p-4 rounded-xl border border-[var(--border-color)] bg-[var(--surface-card)] space-y-3">
          <h3 className="text-sm font-semibold">{t("privx.7")}</h3>
          <ul className="flex flex-wrap gap-2 list-none p-0 m-0">
            {notice.purposes.map(item => (
              <li key={item} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-[var(--border-color)]">
                <Check className="w-3.5 h-3.5 text-[var(--color-primary)] shrink-0" aria-hidden="true" />
                {label(item, t)}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="p-4 rounded-xl border border-[var(--border-color)] bg-[var(--surface-card)] space-y-3">
        <h3 className="text-sm font-semibold">{t("privx.8")}</h3>
        <ul className="space-y-2 list-none p-0 m-0">
          {retentionRows(notice.retention_summary, t).map(row => (
            <li key={row} className="flex items-start gap-2.5 text-sm">
              <span className="w-2 h-2 rounded-full bg-[var(--color-primary)] mt-1.5 shrink-0" aria-hidden="true" />
              <span>{row}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>}
    {notice && <section className="campus-panel space-y-4">
      <h2 className="text-lg font-semibold">{t("privx.9")}</h2>
      {consents.length ? (
        <ul className="space-y-2.5 list-none p-0 m-0">
          {consents.map(record => (
            <li key={record.id} className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl border border-[var(--border-color)] bg-[var(--surface-card)]">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-medium">{label(record.purpose, t)}</span>
                <span> · </span>
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border border-[var(--border-color)] bg-[var(--color-primary-light)] text-[var(--color-primary)]">{label(record.decision, t)}</span>
                <span> · </span>
                <span className="text-xs">{new Date(record.recorded_at).toLocaleString("vi-VN")}</span>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="flex flex-col items-center justify-center text-center py-8 px-4 rounded-xl border border-dashed border-[var(--border-color)] space-y-2">
          <Inbox className="w-8 h-8 opacity-60" aria-hidden="true" />
          <p className="text-sm">{t("privx.10")}</p>
        </div>
      )}
      <p className="text-xs leading-relaxed">{t("privx.11")}</p>
    </section>}
    <nav className="flex flex-col sm:flex-row gap-3 pt-2">
      <Link href="/tickets" className="inline-flex items-center justify-center gap-2 min-h-[44px] px-5 py-2.5 rounded-xl border border-[var(--border-color)] bg-[var(--surface-card)] text-sm font-medium hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]">
        <FileText className="w-4 h-4 shrink-0" aria-hidden="true" />
        <span>{t("privx.12")}</span>
      </Link>
      <Link href="/chat" className="inline-flex items-center justify-center gap-2 min-h-[44px] px-5 py-2.5 rounded-xl border border-[var(--border-color)] bg-[var(--surface-card)] text-sm font-medium hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]">
        <MessageSquare className="w-4 h-4 shrink-0" aria-hidden="true" />
        <span>{t("privx.13")}</span>
      </Link>
    </nav>
  </div></AppShell>;
}
