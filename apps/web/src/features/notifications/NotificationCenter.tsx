"use client";
import { useT } from "@/lib/i18n";
import Link from "next/link";
import { Bell, Inbox, SlidersHorizontal } from "lucide-react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AssistantTrackingClient, type Notification, type Subscription, type TrackingTrigger } from "@/lib/assistant-tracking";
import { AssistantStateService, assistantClientId, type AssistantGrant } from "@/lib/assistant-state-service";
import type { PersonalPreview } from "@/lib/assistant-memory";
import { useUnifiedAssistant, useOptionalUnifiedAssistant } from "@/lib/unified-assistant-runtime";
import { useStore } from "@/lib/store";

const client = new AssistantTrackingClient(), grantsClient = new AssistantStateService();
export function NotificationCenter() {
  const t = useT();
  const runtime = useOptionalUnifiedAssistant();
  const { dataConfig } = useStore();
  return runtime?.actor && runtime.capabilities ? <ActorNotifications key={`${dataConfig?.mode}:${runtime.capabilities.tenant_id}:${runtime.actor.user_id}:${runtime.actor.roles.join(",")}`} /> : <section className="campus-empty-state"><Bell size={32} /><h2>{t("ncx.1")}</h2><p>{t("ncx.2")}</p><Link href="/login" className="fluent-btn-primary">{t("ncx.3")}</Link></section>;
}
function ActorNotifications() {
  const t = useT();
  const runtime = useUnifiedAssistant();
  const router = useRouter();
  const [items, setItems] = useState<Notification[]>([]), [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [grants, setGrants] = useState<AssistantGrant[]>([]), [grantId, setGrantId] = useState("");
  const [trigger, setTrigger] = useState<TrackingTrigger>("status"), [configured, setConfigured] = useState(false);
  const [pending, setPending] = useState<{ preview: PersonalPreview; clientId: string; label: string } | null>(null);
  const [confirmed, setConfirmed] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [cursor, setCursor] = useState<string | null>(null), [message, setMessage] = useState("");
  const [opened, setOpened] = useState<(Awaited<ReturnType<typeof client.open>> & { event_id: string }) | null>(null);
  async function load() { const subs = await client.subscriptions(); await runtime.guard(); setSubscriptions(subs.items); setConfigured(subs.configured); if (subs.configured) { const page = await client.notifications(); await runtime.guard(); setItems(page.items); setCursor(page.next_cursor); } const page = await grantsClient.grants(); await runtime.guard(); setGrants(page.items.filter(g => g.state === "active" && g.capability === "read_source" && g.lifetime !== "once" && !g.locked_reason)); }
  async function run(work: () => Promise<void>) { setBusy(true); setError(""); try { await runtime.guard(); await work(); } catch (e) { setError(e instanceof Error ? e.message : t("ncx.4")); } finally { setBusy(false); } }
  useEffect(() => { void run(load); }, []); // Explicit user readback refreshes the current session.
  async function stop(subscription: Subscription) { const clientId = assistantClientId(); setPending({ preview: await client.preview(subscription.key, null, subscription.version, clientId), clientId, label: t("ncx.45", { id: subscription.payload.spec.resource.id, e: subscription.payload.spec.trigger, v: subscription.version }) }); setConfirmed(false); }
  async function readback() { if (!pending) return; const receipt = await client.receipt(pending.clientId); if (receipt.client_id !== pending.clientId || receipt.state !== "committed") throw new Error(t("ncx.5")); await load(); setMessage(t("ncx.46", { v: receipt.version })); setPending(null); }
  return (
    <section className="campus-notifications space-y-5" aria-label={t("ncx.6")}>
      <div className="fluent-card border border-[var(--border-color)] bg-[var(--surface-card)] p-5 space-y-2">
        <h2 className="text-xl font-semibold text-[var(--text-primary)]">{t("ncx.7")}</h2>
        <p className="text-sm text-[var(--text-secondary)]">
          {t("ncx.8")}
        </p>
      </div>

      {error && (
        <p
          role="alert"
          className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300"
        >
          {error} {t("ncx.9")}
        </p>
      )}
      {message && (
        <p
          role="status"
          className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300"
        >
          {message}
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <button className="fluent-btn-secondary" disabled={busy} onClick={() => void run(load)}>
          {t("ncx.10")}
        </button>
        {!configured && (
          <p role="status" className="text-sm font-medium text-[var(--text-secondary)]">
            {t("ncx.11")}
          </p>
        )}
      </div>

      <details className="fluent-card border border-[var(--border-color)] bg-[var(--surface-card)] p-5 campus-notification-preferences">
        <summary className="flex cursor-pointer items-center gap-2 font-semibold text-[var(--text-primary)]">
          <SlidersHorizontal size={18} />
          {t("ncx.12")}
        </summary>
        <div className="mt-4 space-y-4">
          <label className="block text-sm font-medium text-[var(--text-primary)]">
            {t("ncx.13")}
            <select
              className="fluent-input mt-1"
              value={grantId}
              onChange={(e) => setGrantId(e.target.value)}
            >
              <option value="">{t("ncx.14")}</option>
              {grants.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.resource.kind} {g.resource.id} · v{g.resource.expected_version} · {t("ncx.48", { d: g.expires_at })}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-medium text-[var(--text-primary)]">
            {t("ncx.15")}
            <select
              className="fluent-input mt-1"
              value={trigger}
              onChange={(e) => setTrigger(e.target.value as TrackingTrigger)}
            >
              <option value="status">{t("ncx.16")}</option>
              <option value="feedback">{t("ncx.17")}</option>
              <option value="supplement">{t("ncx.18")}</option>
              <option value="deadline" disabled>
                {t("ncx.19")}
              </option>
            </select>
          </label>
          <p className="text-xs text-[var(--text-secondary)]">
            {t("ncx.20")}
          </p>
          <button
            className="fluent-btn-primary"
            disabled={!configured || !grantId || busy || Boolean(pending)}
            onClick={() =>
              void run(async () => {
                const grant = grants.find((g) => g.id === grantId);
                if (!grant) throw new Error(t("ncx.21"));
                const clientId = assistantClientId();
                setPending({
                  preview: await client.preview(
                    clientId,
                    {
                      resource: grant.resource,
                      trigger,
                      channel: "in_app",
                      expires_at: grant.expires_at,
                      permission_id: grant.id,
                      permission_version: grant.version,
                      quiet_start_hour: 22,
                      quiet_end_hour: 7,
                      utc_offset_minutes: 420,
                    },
                    0,
                    clientId
                  ),
                  clientId,
                  label: t("ncx.47", { e: trigger, id: grant.resource.id, v: grant.resource.expected_version, d: grant.expires_at }),
                });
                setConfirmed(false);
              })
            }
          >
            {t("ncx.22")}
          </button>
          {subscriptions.map((s) => (
            <article className="fluent-card border border-[var(--border-color)] bg-[var(--surface-subtle)] p-3 text-xs" key={s.key}>
              <p className="font-semibold text-[var(--text-primary)]">
                {s.payload.spec.resource.id} · {s.payload.spec.trigger} · {s.payload.state} · v{s.version}
              </p>
              <p className="text-[var(--text-secondary)]">{t("ncx.49", { d: s.payload.spec.expires_at })}</p>
              {s.payload.state === "active" && (
                <button
                  className="fluent-btn-secondary text-xs mt-2"
                  disabled={busy || Boolean(pending)}
                  onClick={() => void run(() => stop(s))}
                >
                  {t("ncx.23")}
                </button>
              )}
            </article>
          ))}
        </div>
      </details>

      <div className="campus-filter-chips" role="group" aria-label={t("ncx.24")}>
        {[
          ["all", t("ncx.25")],
          ["public_student", t("ncx.26")],
          ["internal_staff", t("ncx.27")],
        ].map(([value, label]) => (
          <button
            type="button"
            key={value}
            aria-pressed={filter === value}
            onClick={() => setFilter(value)}
          >
            {label}
            <span>
              {value === "all"
                ? items.length
                : items.filter((item) => item.classification === value).length}
            </span>
          </button>
        ))}
      </div>

      {!busy && !items.filter((item) => filter === "all" || item.classification === filter).length && (
        <div className="campus-empty-state" role="status">
          <Inbox size={32} />
          <h3>{t("ncx.28")}</h3>
          <p>{t("ncx.29")}</p>
        </div>
      )}

      {items
        .filter((item) => filter === "all" || item.classification === filter)
        .map((n) => (
          <article key={n.id} className="campus-notification-card">
            <span className="campus-notification-icon">
              <Bell size={20} />
            </span>
            <div>
              <p className="font-semibold text-[var(--text-primary)]">{n.reason}</p>
              <p className="text-xs text-[var(--text-secondary)]">
                {t("ncx.50", { s: n.source_id, u: n.updated_at })} ·{" "}
                {n.audience === "staff" ? t("ncx.27") : t("ncx.30")}
              </p>
              <p className="text-xs text-[var(--text-secondary)]">{t("ncx.51", { a: n.next_action })}</p>
              <p className="text-xs text-[var(--text-secondary)]">
                {t("ncx.52", { id: n.resource.id, v: n.resource.expected_version })}
              </p>
              <div className="flex flex-wrap gap-2 pt-2">
                <button
                  className="fluent-btn-secondary text-xs"
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      const result = await client.open(n.event_id);
                      await runtime.guard();
                      if (
                        result.action_authority !== "none" ||
                        result.resource.id !== n.resource.id ||
                        result.resource.kind !== n.resource.kind ||
                        result.resource.expected_version !== n.resource.expected_version
                      )
                        throw new Error(t("ncx.31"));
                      setOpened({ ...result, event_id: n.event_id });
                    })
                  }
                >
                  {t("ncx.32")}
                </button>
                <button
                  className="fluent-btn-secondary text-xs"
                  disabled={busy || Boolean(pending)}
                  onClick={() =>
                    void run(async () => {
                      const subscription = subscriptions.find((s) => s.key === n.subscription_id);
                      if (!subscription) throw new Error(t("ncx.33"));
                      await stop(subscription);
                    })
                  }
                >
                  {t("ncx.34")}
                </button>
              </div>
            </div>
          </article>
        ))}

      {opened && (
        <section className="fluent-card border border-[var(--border-color)] bg-[var(--surface-card)] p-4 space-y-3" aria-label={t("ncx.35")}>
          <p className="text-sm font-bold text-[var(--text-primary)]">
            {t("ncx.53", { id: opened.resource.id, v: opened.resource.expected_version })}
          </p>
          {opened.handover.map((handover, index) => (
            <div key={index} className="rounded-lg bg-[var(--surface-subtle)] p-3 text-xs space-y-1">
              <p className="font-semibold text-[var(--color-primary)]">
                {handover.summary.visibility === "public" ? t("ncx.36") : t("ncx.37")} · {handover.queue}
              </p>
              <p className="text-[var(--text-secondary)]">{t("ncx.54", { v: handover.summary.done.join("; ") })}</p>
              <p className="text-[var(--text-secondary)]">{t("ncx.55", { v: handover.summary.open.join("; ") })}</p>
              <p className="text-[var(--text-secondary)]">{t("ncx.56", { v: handover.summary.next_action })}</p>
            </div>
          ))}
          <button
            className="fluent-btn-primary text-xs"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                const fresh = await client.open(opened.event_id);
                await runtime.guard();
                const prefix =
                  fresh.resource.kind === "service_request"
                    ? "/services"
                    : runtime.capabilities?.audience === "staff"
                    ? "/staff"
                    : "/tickets";
                if (
                  fresh.resource.id !== opened.resource.id ||
                  fresh.resource.expected_version !== opened.resource.expected_version ||
                  fresh.open_path !== `${prefix}?request=${fresh.resource.id}`
                )
                  throw new Error(t("ncx.38"));
                router.push(fresh.open_path);
              })
            }
          >
            {t("ncx.39")}
          </button>
        </section>
      )}

      {cursor && (
        <button
          className="fluent-btn-secondary"
          disabled={busy}
          onClick={() =>
            void run(async () => {
              const page = await client.notifications(cursor);
              await runtime.guard();
              setItems((previous) => [...previous, ...page.items]);
              setCursor(page.next_cursor);
            })
          }
        >
          {t("ncx.40")}
        </button>
      )}

      {pending && (
        <section className="fluent-card border border-[var(--color-primary-border)] bg-[var(--color-primary-subtle)] p-5 space-y-3" aria-label={t("ncx.22")}>
          <p className="text-sm font-semibold text-[var(--text-primary)]">{pending.label}</p>
          <p className="text-xs text-[var(--text-secondary)]">{t("ncx.57", { d: pending.preview.expires_at })}</p>
          <label className="flex items-center gap-2 text-sm text-[var(--text-primary)] cursor-pointer">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              className="accent-[var(--color-primary)]"
            />
            <span>{t("ncx.41")}</span>
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              className="fluent-btn-primary"
              disabled={!confirmed || busy}
              onClick={() =>
                void run(async () => {
                  await client.confirm(pending.preview);
                  await readback();
                })
              }
            >
              {t("ncx.42")}
            </button>
            <button
              className="fluent-btn-secondary"
              disabled={busy}
              onClick={() => void run(readback)}
            >
              {t("ncx.43")}
            </button>
            <button
              className="fluent-btn-secondary"
              disabled={busy}
              onClick={() => setPending(null)}
            >
              {t("ncx.44")}
            </button>
          </div>
        </section>
      )}
    </section>
  );
}
