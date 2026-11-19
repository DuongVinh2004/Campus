"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useSyncExternalStore,
} from "react";
import { useStore } from "@/lib/store";

export interface TicketDraftData {
  certDestinationOrg: string;
  certPurpose: string;
  certValidUntil: string;
  certNotes: string;
  hasUnsavedChanges: boolean;
  revision: number;
}

interface DraftContextValue {
  getDraft: (ticketId: string) => TicketDraftData | undefined;
  setDraft: (ticketId: string, draft: TicketDraftData) => void;
  clearDraft: (ticketId: string) => void;
  getSnapshot: (ticketId: string) => TicketDraftSnapshot;
  subscribe: (ticketId: string, listener: () => void) => () => void;
  acquireOperation: (ticketId: string, kind: DraftOperationKind) => string | null;
  releaseOperation: (ticketId: string, token: string) => void;
}

export type DraftOperationKind = "save" | "sync" | "submit";

export interface DraftOperation {
  kind: DraftOperationKind;
  token: string;
}

export interface TicketDraftSnapshot {
  draft: TicketDraftData | undefined;
  operation: DraftOperation | null;
}

interface TicketRuntime {
  draft: TicketDraftData | undefined;
  operation: DraftOperation | null;
  listeners: Set<() => void>;
  snapshot: TicketDraftSnapshot;
}

const EMPTY_SNAPSHOT: TicketDraftSnapshot = {
  draft: undefined,
  operation: null,
};

const DraftContext = createContext<DraftContextValue | null>(null);

function DraftSessionInner({ children }: { children: React.ReactNode }) {
  const runtimesRef = useRef(new Map<string, TicketRuntime>());
  const operationSequenceRef = useRef(0);

  const getRuntime = useCallback((ticketId: string): TicketRuntime => {
    const existing = runtimesRef.current.get(ticketId);
    if (existing) return existing;

    const runtime: TicketRuntime = {
      draft: undefined,
      operation: null,
      listeners: new Set(),
      snapshot: EMPTY_SNAPSHOT,
    };
    runtimesRef.current.set(ticketId, runtime);
    return runtime;
  }, []);

  const notify = useCallback((runtime: TicketRuntime) => {
    runtime.listeners.forEach((listener) => listener());
  }, []);

  const publish = useCallback(
    (runtime: TicketRuntime) => {
      runtime.snapshot = {
        draft: runtime.draft,
        operation: runtime.operation,
      };
      notify(runtime);
    },
    [notify]
  );

  const value = useMemo<DraftContextValue>(
    () => ({
      getDraft: (ticketId) => runtimesRef.current.get(ticketId)?.draft,
      setDraft: (ticketId, draft) => {
        const runtime = getRuntime(ticketId);
        runtime.draft = { ...draft };
        publish(runtime);
      },
      clearDraft: (ticketId) => {
        const runtime = runtimesRef.current.get(ticketId);
        if (!runtime || !runtime.draft) return;
        runtime.draft = undefined;
        publish(runtime);
      },
      getSnapshot: (ticketId) => runtimesRef.current.get(ticketId)?.snapshot ?? EMPTY_SNAPSHOT,
      subscribe: (ticketId, listener) => {
        const runtime = getRuntime(ticketId);
        runtime.listeners.add(listener);
        return () => {
          runtime.listeners.delete(listener);
          if (!runtime.listeners.size && !runtime.draft && !runtime.operation) {
            runtimesRef.current.delete(ticketId);
          }
        };
      },
      acquireOperation: (ticketId, kind) => {
        const runtime = getRuntime(ticketId);
        if (runtime.operation) return null;

        const token = `${operationSequenceRef.current++}`;
        runtime.operation = { kind, token };
        publish(runtime);
        return token;
      },
      releaseOperation: (ticketId, token) => {
        const runtime = runtimesRef.current.get(ticketId);
        if (!runtime || runtime.operation?.token !== token) return;

        runtime.operation = null;
        publish(runtime);
        if (!runtime.listeners.size && !runtime.draft) {
          runtimesRef.current.delete(ticketId);
        }
      },
    }),
    [getRuntime, publish]
  );

  return <DraftContext.Provider value={value}>{children}</DraftContext.Provider>;
}

export function DraftSessionProvider({ children }: { children: React.ReactNode }) {
  const { currentUser } = useStore();
  const key = currentUser ? `${currentUser.id}-${currentUser.role}` : "anonymous";

  return <DraftSessionInner key={key}>{children}</DraftSessionInner>;
}

export function useDraftSession() {
  const context = useContext(DraftContext);
  if (!context) throw new Error("useDraftSession must be used within DraftSessionProvider");
  return context;
}

export function useTicketDraftSession(ticketId: string): TicketDraftSnapshot {
  const context = useDraftSession();
  const subscribe = useCallback(
    (listener: () => void) => context.subscribe(ticketId, listener),
    [context, ticketId]
  );
  const getSnapshot = useCallback(
    () => context.getSnapshot(ticketId),
    [context, ticketId]
  );
  const getServerSnapshot = useCallback(() => EMPTY_SNAPSHOT, []);

  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
