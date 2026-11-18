"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";
import { useEffect, useState } from "react";
import { AssistantMemoryClient, type MemoryItem, type MemoryPage, type MemoryValue, type PersonalPreview } from "@/lib/assistant-memory";
import { assistantClientId } from "@/lib/assistant-state-service";
import { useOptionalUnifiedAssistant } from "@/lib/unified-assistant-runtime";
import { useStore } from "@/lib/store";

const client = new AssistantMemoryClient();
const buffers = new Map<string, { topic: string; text: string; kind: MemoryValue["kind"]; editing: MemoryItem | null }>();

export function MemoryCenter() {
  const runtime = useOptionalUnifiedAssistant();
  const { dataConfig } = useStore();
  const actorKey = runtime?.actor && runtime.capabilities ? `${CAMPUS_API_BASE_URL}:${dataConfig?.mode}:${runtime.capabilities.tenant_id}:${runtime.actor.user_id}:${[...runtime.actor.roles].sort().join(",")}` : "";
  return actorKey && runtime ? <ActorMemory key={actorKey} actorKey={actorKey} guard={runtime.guard} /> : <p role="status">Cần xác nhận phiên và vai trò để mở memory.</p>;
}

function ActorMemory({ actorKey, guard }: { actorKey: string; guard: () => Promise<unknown> }) {
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
  async function run(work: () => Promise<void>) { setBusy(true); setError(""); try { await guard(); await work(); await guard(); } catch (e) { setError(e instanceof Error ? e.message : "Chưa xác minh kết quả; giữ nội dung soạn."); } finally { setBusy(false); } }
  async function prepare(change: Parameters<typeof client.preview>[0], version: number) {
    const clientId = assistantClientId(), preview = await client.preview(change, version, clientId);
    const label = change.operation === "save" ? `Lưu ${change.value.topic}: ${change.value.text}. Hiệu lực đến ${change.value.valid_until}. Phiên bản hiện tại ${version}.` : change.operation === "forget" ? `Quên topic đã chọn tại phiên bản ${version}; ngăn sử dụng và tái tạo, giữ dữ liệu cũ để bảo toàn. Chưa xóa vật lý.` : `${change.enabled ? "Bật" : "Tắt"} memory cá nhân theo các lựa chọn riêng tư hiển thị ở trên. Không xóa history.`;
    setPending({ preview, clientId, label }); setConfirmed(false);
  }
  async function readback() {
    if (!pending) return;
    const receipt = await client.receipt(pending.clientId);
    if (receipt.client_id !== pending.clientId || receipt.state !== "committed") throw new Error("Receipt chưa khớp; giữ bản soạn.");
    const next = await client.read(); await guard(); setPage(next);
    setMessage(`Đã commit và đọc lại phiên bản ${receipt.version}. Nội dung soạn được giữ.`);
    setPending(null); setConfirmed(false);
  }
  return (
    <section aria-label="Memory cá nhân" className="space-y-5">
      <div className="fluent-card border border-[var(--border-color)] bg-[var(--surface-card)] p-5 space-y-2">
        <h2 className="text-xl font-semibold text-[var(--text-primary)]">Memory cá nhân</h2>
        <p className="text-sm text-[var(--text-secondary)]">
          Chỉ lưu điều bạn chủ động xác nhận. Khai báo cá nhân không thay nguồn học vụ hay quyền nghiệp vụ. Tắt memory không xóa history; chat tạm thời không đọc hoặc ghi memory.
        </p>
        <p className="text-sm text-[var(--text-secondary)]">
          Quên ngăn sử dụng và tái tạo topic bằng tombstone. Dữ liệu cũ, history, index và backup vẫn được giữ; chưa thực hiện xóa vật lý. Export tại đây chỉ gồm memory hiện còn được phép đọc.
        </p>
        <p className="text-sm text-[var(--text-secondary)]">
          Sau khi quên, lịch sử vẫn đọc được nhưng không tự đưa vào context model để tránh khôi phục nội dung đã quên. Bạn có thể chủ động nêu lại thông tin cần dùng trong câu hỏi hiện tại.
        </p>
      </div>

      {error && (
        <p
          role="alert"
          className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300"
        >
          {error} Nội dung và preview được giữ để kiểm tra receipt hoặc thử đọc lại.
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
              Memory: {page.control?.payload.enabled ? "Đã bật theo xác nhận riêng" : "Đang tắt"}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <button
              className="fluent-btn-secondary"
              disabled={busy}
              onClick={() => void run(async () => setPage(await client.read()))}
            >
              Đọc lại
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
                Xem trước {page.control?.payload.enabled ? "tắt" : "bật"} memory
              </button>
            )}
          </div>
        </div>

        <div className="grid gap-3">
          <label className="flex flex-col gap-1 text-sm font-medium text-[var(--text-primary)]">
            Loại
            <select
              className="fluent-input"
              value={kind}
              disabled={Boolean(editing)}
              onChange={(e) => setKind(e.target.value as MemoryValue["kind"])}
            >
              <option value="preference">Sở thích</option>
              <option value="goal">Mục tiêu</option>
              <option value="confirmed_fact">Điều cá nhân tôi xác nhận</option>
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
            Nội dung
            <textarea
              className="fluent-input"
              maxLength={1000}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </label>
        </div>

        <p className="text-xs text-[var(--text-secondary)]">
          Memory mới có hiệu lực 30 ngày. Khi sửa giữ thời hạn đã lưu. Không nhập nội dung hồ sơ của người khác.
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
            Xem trước {editing ? "sửa" : "lưu"}
          </button>
          {editing && (
            <button
              className="fluent-btn-secondary"
              onClick={() => setEditing(null)}
            >
              Giữ nội dung, chuyển sang mục mới
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
                ? "Topic đã quên — ngăn tái tạo"
                : item.value?.topic || item.locked_reason}{" "}
              · v{item.version} · {item.updated_at}
            </p>
            {item.value && (
              <>
                <p className="text-sm text-[var(--text-primary)]">{item.value.text}</p>
                <p className="text-xs text-[var(--text-secondary)]">
                  Hết hiệu lực: {item.value.valid_until}
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
                  Sửa bản hiện hành
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
                  Xem trước quên
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
            Đọc thêm
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
          Đọc trang export memory hiện hành
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
          aria-label="Xem trước memory"
        >
          <p className="text-xs font-semibold text-[var(--color-primary)]">
            Hiệu lực preview đến {pending.preview.expires_at}
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
            <span>Tôi xác nhận nội dung, thời hạn và phạm vi trên</span>
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
              Xác nhận và đọc lại
            </button>
            <button
              className="fluent-btn-secondary"
              disabled={busy}
              onClick={() => void run(readback)}
            >
              Kiểm tra receipt
            </button>
            <button
              className="fluent-btn-secondary"
              disabled={busy}
              onClick={() => setPending(null)}
            >
              Đóng preview, giữ bản soạn
            </button>
          </div>
        </section>
      )}
    </section>
  );
}
