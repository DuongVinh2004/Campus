"use client";
import { useT } from "@/lib/i18n";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";
import { useEffect, useState } from "react";
import { AssistantMemoryClient, type MemoryItem, type MemoryPage, type MemoryValue, type PersonalPreview } from "@/lib/assistant-memory";
import { assistantClientId } from "@/lib/assistant-state-service";
import { useOptionalUnifiedAssistant } from "@/lib/unified-assistant-runtime";
import { useStore } from "@/lib/store";

const client = new AssistantMemoryClient();
const buffers = new Map<string, { topic: string; text: string; kind: MemoryValue["kind"]; editing: MemoryItem | null }>();

export function MemoryCenter() {
  const t = useT();
  const runtime = useOptionalUnifiedAssistant();
  const { dataConfig } = useStore();
  // Without the assistant runtime there is nothing to sign in to: say the feature is off instead of blaming the session.
  if (!runtime) return <p role="status">{t("mcx.off")}</p>;
  const actorKey = runtime?.actor && runtime.capabilities ? `${CAMPUS_API_BASE_URL}:${dataConfig?.mode}:${runtime.capabilities.tenant_id}:${runtime.actor.user_id}:${[...runtime.actor.roles].sort().join(",")}` : "";
  return actorKey && runtime ? <ActorMemory key={actorKey} actorKey={actorKey} guard={runtime.guard} /> : <p role="status">{t("mcx.1")}</p>;
}

function ActorMemory({ actorKey, guard }: { actorKey: string; guard: () => Promise<unknown> }) {
  const t = useT();
  const retained = buffers.get(actorKey);
  const [page, setPage] = useState<MemoryPage | null>(null);
  const [topic, setTopic] = useState(retained?.topic || "");
  const [text, setText] = useState(retained?.text || "");
  const [kind, setKind] = useState<MemoryValue["kind"]>(retained?.kind || "preference");
  const [editing, setEditing] = useState<MemoryItem | null>(retained?.editing || null);
  const [pending, setPending] = useState<{ preview: PersonalPreview; clientId: string; label: string } | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [exported, setExported] = useState("");
  useEffect(() => { buffers.set(actorKey, { topic, text, kind, editing }); }, [actorKey, topic, text, kind, editing]);
  useEffect(() => { let active = true; void guard().then(() => client.read()).then(value => { if (active) setPage(value); }).catch(e => { if (active) setError(String(e)); }); return () => { active = false; }; }, [actorKey]);
  async function run(work: () => Promise<void>) { setBusy(true); setError(""); try { await guard(); await work(); await guard(); } catch (e) { setError(e instanceof Error ? e.message : t("mcx.2")); } finally { setBusy(false); } }
  async function prepare(change: Parameters<typeof client.preview>[0], version: number) {
    const clientId = assistantClientId(), preview = await client.preview(change, version, clientId);
    const label = change.operation === "save" ? t("mcx.32", { topic: change.value.topic, text: change.value.text, d: change.value.valid_until, v: version }) : change.operation === "forget" ? t("mcx.33", { v: version }) : t(change.enabled ? "mcx.34" : "mcx.new_off");
    setPending({ preview, clientId, label }); setConfirmed(false);
  }
  async function readback() {
    if (!pending) return;
    const receipt = await client.receipt(pending.clientId);
    if (receipt.client_id !== pending.clientId || receipt.state !== "committed") throw new Error(t("mcx.3"));
    const next = await client.read(); await guard(); setPage(next);
    setMessage(t("mcx.35", { v: receipt.version }));
    setPending(null); setConfirmed(false);
  }
  return (
    <section aria-label={t("mcx.4")} className="space-y-5">
      <div className="fluent-card border border-[var(--border-color)] bg-[var(--surface-card)] p-5 space-y-2">
        <h2 className="text-xl font-semibold text-[var(--text-primary)]">{t("mcx.4")}</h2>
        <p className="text-sm text-[var(--text-secondary)]">
          {t("mcx.5")}
        </p>
        <p className="text-sm text-[var(--text-secondary)]">
          {t("mcx.6")}
        </p>
        <p className="text-sm text-[var(--text-secondary)]">
          {t("mcx.7")}
        </p>
      </div>

      {error && (
        <p
          role="alert"
          className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300"
        >
          {error} {t("mcx.36")}
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

      <div className="fluent-card border border-[var(--border-color)] bg-[var(--surface-card)] p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {page && (
            <p className="text-sm font-medium text-[var(--text-primary)]">
              {t("mcx.37")} {page.control?.payload.enabled ? t("mcx.8") : t("mcx.9")}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <button
              className="fluent-btn-secondary"
              disabled={busy}
              onClick={() => void run(async () => setPage(await client.read()))}
            >
              {t("mcx.12")}
            </button>
            {page && (
              <button
                className="fluent-btn-secondary"
                disabled={busy || Boolean(pending)}
                onClick={() =>
                  void run(() =>
                    prepare(
                      { operation: "control", enabled: !page.control?.payload.enabled },
                      page.control?.version || 0
                    )
                  )
                }
              >
                {t("mcx.38", { s: page.control?.payload.enabled ? t("mcx.10") : t("mcx.11") })}
              </button>
            )}
          </div>
        </div>

        <div className="grid gap-3">
          <label className="flex flex-col gap-1 text-sm font-medium text-[var(--text-primary)]">
            {t("mcx.13")}
            <select
              className="fluent-input"
              value={kind}
              disabled={Boolean(editing)}
              onChange={(e) => setKind(e.target.value as MemoryValue["kind"])}
            >
              <option value="preference">{t("mcx.14")}</option>
              <option value="goal">{t("mcx.15")}</option>
              <option value="confirmed_fact">{t("mcx.16")}</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-[var(--text-primary)]">
            Topic
            <input
              className="fluent-input"
              maxLength={100}
              value={topic}
              disabled={Boolean(editing)}
              onChange={(e) => setTopic(e.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-[var(--text-primary)]">
            {t("mcx.17")}
            <textarea
              className="fluent-input"
              maxLength={1000}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </label>
        </div>

        <p className="text-xs text-[var(--text-secondary)]">
          {t("mcx.18")}
        </p>

        <div className="flex flex-wrap gap-2">
          <button
            className="fluent-btn-primary"
            disabled={!topic.trim() || !text.trim() || busy || Boolean(pending)}
            onClick={() =>
              void run(() =>
                prepare(
                  {
                    operation: "save",
                    value: {
                      kind,
                      topic,
                      text,
                      valid_until:
                        editing?.value?.valid_until ||
                        new Date(Date.now() + 30 * 86400000).toISOString(),
                    },
                  },
                  editing?.version || 0
                )
              )
            }
          >
            {t("mcx.39", { s: editing ? t("mcx.19") : t("mcx.20") })}
          </button>
          {editing && (
            <button
              className="fluent-btn-secondary"
              onClick={() => setEditing(null)}
            >
              {t("mcx.21")}
            </button>
          )}
        </div>
      </div>

      <div className="space-y-3">
        {page?.items.map((item) => (
          <article
            key={item.key}
            className="campus-memory-item fluent-card border border-[var(--border-color)] bg-[var(--surface-card)] p-4 space-y-2"
          >
            <p className="text-xs font-semibold text-[var(--color-primary)]">
              {item.state === "suppressed"
                ? t("mcx.22")
                : item.value?.topic || item.locked_reason}{" "}
              · {t("mcx.40", { v: item.version })} · {item.updated_at}
            </p>
            {item.value && (
              <>
                <p className="text-sm text-[var(--text-primary)]">{item.value.text}</p>
                <p className="text-xs text-[var(--text-secondary)]">
                  {t("mcx.41", { d: item.value.valid_until })}
                </p>
              </>
            )}
            <div className="flex flex-wrap gap-2 pt-1">
              {item.value && (
                <button
                  className="fluent-btn-secondary text-xs"
                  disabled={busy || Boolean(pending)}
                  onClick={() => {
                    setEditing(item);
                    setTopic(item.value!.topic);
                    setText(item.value!.text);
                    setKind(item.value!.kind);
                  }}
                >
                  {t("mcx.23")}
                </button>
              )}
              {item.state === "active" && (
                <button
                  className="fluent-btn-secondary text-xs"
                  disabled={busy || Boolean(pending)}
                  onClick={() =>
                    void run(() =>
                      prepare({ operation: "forget", key: item.key }, item.version)
                    )
                  }
                >
                  {t("mcx.24")}
                </button>
              )}
            </div>
          </article>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        {page?.next_cursor && (
          <button
            className="fluent-btn-secondary"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                const next = await client.read(page.next_cursor!);
                setPage({ ...next, items: [...page.items, ...next.items] });
              })
            }
          >
            {t("mcx.25")}
          </button>
        )}
        <button
          className="fluent-btn-secondary"
          disabled={busy}
          onClick={() =>
            void run(async () =>
              setExported(JSON.stringify(await client.exportPage(), null, 2))
            )
          }
        >
          {t("mcx.26")}
        </button>
      </div>

      {exported && (
        <pre className="fluent-card border border-[var(--border-color)] bg-[var(--surface-subtle)] p-4 text-xs whitespace-pre-wrap break-all font-mono text-[var(--text-primary)]">
          {exported}
        </pre>
      )}

      {pending && (
        <section
          className="fluent-card border border-[var(--color-primary-border)] bg-[var(--color-primary-subtle)] p-5 space-y-3"
          aria-label={t("mcx.27")}
        >
          <p className="text-xs font-semibold text-[var(--color-primary)]">
            {t("mcx.42", { d: pending.preview.expires_at })}
          </p>
          <p className="whitespace-pre-wrap text-sm text-[var(--text-primary)]">
            {pending.label}
          </p>
          <label className="flex items-center gap-2 text-sm text-[var(--text-primary)] cursor-pointer">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              className="accent-[var(--color-primary)]"
            />
            <span>{t("mcx.28")}</span>
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
              {t("mcx.29")}
            </button>
            <button
              className="fluent-btn-secondary"
              disabled={busy}
              onClick={() => void run(readback)}
            >
              {t("mcx.30")}
            </button>
            <button
              className="fluent-btn-secondary"
              disabled={busy}
              onClick={() => setPending(null)}
            >
              {t("mcx.31")}
            </button>
          </div>
        </section>
      )}
    </section>
  );
}
