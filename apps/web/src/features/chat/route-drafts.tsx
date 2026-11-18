"use client";

import React, { createContext, useCallback, useContext, useRef, useState, useSyncExternalStore } from "react";
import { ChatPanel, type ChatPanelProps } from "./ChatPanel";

type DraftStore = {
  values: Map<string, unknown>;
  listeners: Set<() => void>;
};
const DraftContext = createContext<DraftStore | null>(null);
const ActorContext = createContext<string | null>(null);
export const ChatDraftActor = ActorContext.Provider;
export type DraftSendLifecycle = { created: (id: string) => boolean; accepted: () => void };
type PendingQuestion = { text: string };
const EMPTY_PENDING: readonly PendingQuestion[] = [];

export function useTabDraftOwner() {
  return { enabled: useContext(DraftContext) !== null, scope: useContext(ActorContext) };
}

export function useActorRouteState<T>(scope: string | null, name: string, initial: T | (() => T)) {
  const store = useContext(DraftContext);
  const [local, setLocal] = useState<T>(initial);
  const key = store && scope ? JSON.stringify(["workspace", scope, name]) : null;
  const subscribe = useCallback((listener: () => void) => {
    store?.listeners.add(listener);
    return () => { store?.listeners.delete(listener); };
  }, [store]);
  const snapshot = useCallback(() => key && store?.values.has(key)
    ? store.values.get(key) as T : local, [key, store, local]);
  const value = useSyncExternalStore(subscribe, snapshot, () => local);
  const update: React.Dispatch<React.SetStateAction<T>> = useCallback(next => {
    if (!key || !store) { setLocal(next); return; }
    const current = store.values.has(key) ? store.values.get(key) as T : local;
    store.values.set(key, typeof next === "function" ? (next as (value: T) => T)(current) : next);
    store.listeners.forEach(listener => listener());
  }, [key, store, local]);
  return [value, update, snapshot] as const;
}

export function chatDraftActorScope(actor: { user_id?: string; subject_id?: string; roles: string[] } | null | undefined) {
  const id = actor?.user_id || actor?.subject_id;
  return id ? JSON.stringify([id, [...new Set(actor!.roles)].sort()]) : null;
}

// Tab memory only: no server submission, browser storage, or account-wide cache.
export function ChatDraftSessionProvider({ children }: { children: React.ReactNode }) {
  const store = useRef<DraftStore>({ values: new Map(), listeners: new Set() });
  return <DraftContext.Provider value={store.current}>{children}</DraftContext.Provider>;
}

export function RouteDraftChatPanel({ draftId, retainUntilAcknowledged = false, ...props }:
  Omit<ChatPanelProps, "onSendMessage"> & { draftId: string; retainUntilAcknowledged?: boolean;
    onSendMessage?: (content: string, lifecycle?: DraftSendLifecycle) => void }) {
  const store = useContext(DraftContext);
  const actor = useContext(ActorContext);
  const key = actor ? JSON.stringify([actor, draftId]) : null;
  const pendingKey = actor ? JSON.stringify(["chat-pending", actor, draftId]) : null;
  const subscribe = useCallback((listener: () => void) => {
    store?.listeners.add(listener);
    return () => { store?.listeners.delete(listener); };
  }, [store]);
  const snapshot = useCallback(() => {
    const value = key ? store?.values.get(key) : undefined;
    return typeof value === "string" ? value : value && typeof value === "object" && "text" in value
      && typeof value.text === "string" ? value.text : undefined;
  }, [store, key]);
  const saved = useSyncExternalStore(subscribe, snapshot, () => undefined);
  const pendingSnapshot = useCallback(() => pendingKey && store?.values.has(pendingKey)
    ? store.values.get(pendingKey) as readonly PendingQuestion[] : EMPTY_PENDING, [store, pendingKey]);
  const pending = useSyncExternalStore(subscribe, pendingSnapshot, () => EMPTY_PENDING);
  if (!store) return <ChatPanel {...props} />;
  if (!key) return <p role="status">Đang kiểm tra tài khoản trước khi mở bản nháp…</p>;
  const update = (value: string) => {
    store.values.set(key, { text: value });
    store.listeners.forEach(listener => listener());
    props.onComposerChange?.(value);
  };
  const send = (content: string) => {
    if (!retainUntilAcknowledged) { props.onSendMessage?.(content); update(""); return; }
    let boundKey = key;
    let boundPendingKey = pendingKey!;
    const composerEntry = store.values.has(key) ? store.values.get(key) : { text: saved ?? props.initialDraft ?? content };
    store.values.set(key, composerEntry);
    const question: PendingQuestion = { text: content };
    const questions = (name: string) => store.values.get(name) as readonly PendingQuestion[] | undefined ?? EMPTY_PENDING;
    store.values.set(boundPendingKey, [...questions(boundPendingKey), question]);
    store.listeners.forEach(listener => listener());
    props.onSendMessage?.(content, {
      created(id) {
        const nextKey = JSON.stringify([actor, id]);
        if (nextKey === boundKey) return true;
        if (store.values.has(nextKey)) return false;
        const nextPendingKey = JSON.stringify(["chat-pending", actor, id]);
        store.values.set(nextKey, store.values.get(boundKey));
        store.values.set(boundKey, { text: "" });
        store.values.set(boundPendingKey, questions(boundPendingKey).filter(item => item !== question));
        store.values.set(nextPendingKey, [...questions(nextPendingKey), question]);
        boundKey = nextKey; boundPendingKey = nextPendingKey;
        store.listeners.forEach(listener => listener());
        return true;
      },
      accepted() {
        // Entry identity also protects a clear/retype with identical characters.
        if (store.values.get(boundKey) === composerEntry) store.values.set(boundKey, { text: "" });
        store.values.set(boundPendingKey, questions(boundPendingKey).filter(item => item !== question));
        store.listeners.forEach(listener => listener());
      },
    });
  };
  return <div className="flex h-full min-h-0 flex-col"><div className="min-h-0 flex-1">
    <ChatPanel {...props} composerValue={saved ?? props.initialDraft ?? ""} onComposerChange={update} onSendMessage={send} />
    </div>{!props.isStreaming && pending.length > 0 && <aside role="status" className="max-h-40 shrink-0 overflow-auto border-t p-3 text-sm">
      <p>Câu hỏi chưa được xác nhận đã lưu. Kiểm tra lịch sử trước khi gửi lại.</p>
      {pending.map((question, index) => <p key={index} className="whitespace-pre-wrap">{question.text}</p>)}
    </aside>}</div>;
}
